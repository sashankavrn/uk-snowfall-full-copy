"""
NCR Voyix - Close/Update ServiceNow Ticket Lambda
------------------------------------------
Invoked asynchronously by snowfall-proactive-alerts when an Athena query
returns no rows for a rule that previously had an open ServiceNow case.

Flow:
  1. Extract the SERVICENOW_CASE record and rule from the event payload.
  2. Resolve the NCR ticket ID:
       a. Use case["ncr_ticket_id"] if already populated.
       b. Otherwise scan SERVICE_NOW_TICKETS_TABLE by source_alert_id.
  3. If no NCR ticket ID can be found (ticket was never created / still
     in-flight), log and exit gracefully.
  4. POST an UpdateServiceRequest payload to the NCR CSDI endpoint.
  5. Update SERVICE_NOW_TICKETS_TABLE ticket row: set resolved_at, close_notes,
     ncr_close_status.
  6. Update PROACTIVE_ALERTS_TABLE case row: status → CLOSED on business success.

Expected invocation event shape:
    {
        "rule": { ...incident rule row... },
        "case": { ...SERVICENOW_CASE row from proactive_alerts_table... }
    }

Environment variables:
    SECRET_NAME               (optional) AWS Secrets Manager secret with NCR creds.
                               Defaults to "uk-snowfall-ncr-servicenow". The secret
                               JSON must contain:
                                 uk-snowfall-ncr-servicenow-url          (CreateServiceRequest URL used
                                                                          as base; /Create is replaced)
                                 uk-snowfall-ncr-servicenow-update-url   (direct update URL, preferred)
                                 uk-snowfall-ncr-servicenow-resolve-url  (fallback)
                                 uk-snowfall-ncr-servicenow-username
                                 uk-snowfall-ncr-servicenow-password
    SECRET_REGION             (optional) defaults to "eu-central-1"
    SERVICE_NOW_TICKETS_TABLE e.g. uk-snowfall-dev-service-now-tickets
    PROACTIVE_ALERTS_TABLE    e.g. uk-snowfall-dev-proactive-alerts
    SOURCE_SYSTEM             (optional) defaults to "WS"
    USER_ID                   (optional) defaults to "UKMCD"
    NCR_SOAP_SERVICE_NOW_UPDATE_URL  (optional) direct UpdateServiceRequest URL override
    NCR_VERIFY_SSL            (optional) "true"/"false" - defaults to "false"
"""

import base64
import json
import os
import ssl
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SECRET_NAME = os.environ.get("SECRET_NAME", "uk-snowfall-ncr-servicenow")
SECRET_REGION = os.environ.get("SECRET_REGION", "eu-central-1")

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
PROACTIVE_ALERTS_TABLE = os.environ["PROACTIVE_ALERTS_TABLE"]

SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "WS")
USER_ID = os.environ.get("USER_ID", "UKMCD")
NCR_SOAP_SERVICE_NOW_UPDATE_URL = os.environ.get("NCR_SOAP_SERVICE_NOW_UPDATE_URL", "").strip()
VERIFY_SSL = os.environ.get("NCR_VERIFY_SSL", "false").lower() == "true"

REQUEST_TIMEOUT_SECONDS = 30

RESOLUTION_TEXT = "Closed by Snowfall proactive system as this is triggered by rules defined."

# Cached NCR credentials (populated on first call)
_NCR_CREDS = None

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------

dynamodb = boto3.resource("dynamodb")
tickets_table = dynamodb.Table(SERVICE_NOW_TICKETS_TABLE)
proactive_alerts_table = dynamodb.Table(PROACTIVE_ALERTS_TABLE)


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event, default=str)}")

    rule = event.get("rule") or {}
    case = event.get("case") or {}

    if not case:
        print("[ERROR] No 'case' payload in event; nothing to do.")
        return {"statusCode": 400, "body": json.dumps({"error": "missing 'case' payload"})}

    case_id = case.get("alert_id", "UNKNOWN")
    rule_id = case.get("rule_id", "")
    print(f"Processing close for case {case_id} (rule={rule_id})")

    # Resolve NCR ticket ID
    ncr_ticket_id = _resolve_ncr_ticket_id(case)
    if not ncr_ticket_id:
        print(
            f"[WARN] No NCR ticket ID found for case {case_id}. "
            "Ticket may never have been created or creation is still in-flight. "
            "Marking case as CLOSED without calling NCR."
        )
        _mark_case_closed(case_id, ncr_ticket_id=None, ncr_status="SKIPPED")
        return {
            "statusCode": 200,
            "body": json.dumps({"skipped": True, "reason": "no_ncr_ticket_id", "case_id": case_id}),
        }

    print(f"Resolved NCR ticket ID: {ncr_ticket_id}")

    # Build and send UpdateServiceRequest
    payload = _build_update_payload(ncr_ticket_id, case, rule)
    print(f"NCR update request payload: {json.dumps(payload)}")

    response = _post_to_ncr(payload)
    print(f"NCR update response: {json.dumps(response)}")

    header = response.get("Header", {}) or {}
    ncr_status = (header.get("Status") or "UNKNOWN").upper()
    fault = header.get("Fault") or {}
    incident_update = response.get("IncidentUpdate") or {}
    returned_ticket_id = incident_update.get("TicketID")
    fault_code = fault.get("FaultCode")
    fault_description = fault.get("FaultDescription")

    # Update SERVICE_NOW_TICKETS_TABLE
    _update_ticket_resolved(ncr_ticket_id, ncr_status, fault_description)

    success = ncr_status == "SUCCESS"
    if success:
        # Update PROACTIVE_ALERTS_TABLE case record only on business success.
        _mark_case_closed(case_id, ncr_ticket_id=ncr_ticket_id, ncr_status=ncr_status)
    else:
        print(
            f"[WARN] NCR update returned non-success status for case {case_id} "
            f"(ncr_status={ncr_status}); leaving case state unchanged"
        )


    return {
        "statusCode": 200 if success else 502,
        "body": json.dumps(
            {
                "success": success,
                "case_id": case_id,
                "ncr_ticket_id": ncr_ticket_id,
                "returned_ticket_id": returned_ticket_id,
                "ncr_status": ncr_status,
                "fault_code": fault_code,
                "fault_description": fault_description,
            }
        ),
    }


# ---------------------------------------------------------------------------
# NCR ticket ID resolution
# ---------------------------------------------------------------------------

def _resolve_ncr_ticket_id(case: dict):
    """Return the NCR ticket ID from the case record or by looking it up
    in SERVICE_NOW_TICKETS_TABLE via source_alert_id."""
    ncr_ticket_id = case.get("ncr_ticket_id")
    if ncr_ticket_id:
        return str(ncr_ticket_id).strip() or None

    source_alert_id = case.get("source_alert_id")
    if not source_alert_id:
        return None

    print(f"ncr_ticket_id not in case; looking up by source_alert_id={source_alert_id}")

    # Scan for the ticket row created by the creation Lambda
    response = tickets_table.scan(
        FilterExpression=Attr("alert_id").eq(source_alert_id) & Attr("status").eq("SUCCESS"),
        ProjectionExpression="ticket_id, ncr_ticket_id",
    )
    items = response.get("Items", [])

    while response.get("LastEvaluatedKey"):
        response = tickets_table.scan(
            FilterExpression=Attr("alert_id").eq(source_alert_id) & Attr("status").eq("SUCCESS"),
            ProjectionExpression="ticket_id, ncr_ticket_id",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    if not items:
        print(f"[WARN] No SUCCESS ticket found for source_alert_id={source_alert_id}")
        return None

    ncr_id = str(items[0].get("ncr_ticket_id") or "").strip()
    return ncr_id or None


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def _build_update_payload(ncr_ticket_id: str, case: dict, rule: dict) -> dict:
    transaction_id = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    description = str(rule.get("incident_description") or "Snowfall proactive alert").splitlines()[0]
    customer_ticket_id = str(
        case.get("source_alert_id")
        or case.get("customer_ticket_id")
        or case.get("alert_id")
        or ncr_ticket_id
    )
    country_code = str(case.get("country_code") or rule.get("country_code") or "UK")

    return {
        "Header": {
            "TransactionID": transaction_id,
            "USERID": USER_ID,
            "SourceSystem": SOURCE_SYSTEM,
            "TimeStamp": timestamp,
        },
        "UpdateServiceRequest": {
            "CustomerTicketID": customer_ticket_id,
            "TicketID": ncr_ticket_id,
            "CountryCode": country_code,
            "ResolutionNotes": RESOLUTION_TEXT,
            "Remark": {
                "Text": (
                    f"Close request for Snowfall proactive ticket {ncr_ticket_id}. "
                    f"Rule: {description}."
                )
            },
        },
    }


# ---------------------------------------------------------------------------
# NCR HTTP call
# ---------------------------------------------------------------------------

def _get_ncr_credentials():
    """Fetch NCR URL + credentials from AWS Secrets Manager. Cached per container."""
    global _NCR_CREDS
    if _NCR_CREDS is not None:
        return _NCR_CREDS

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=SECRET_REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])

    # Prefer env override, then dedicated update URL, fallback to resolve URL,
    # then derive from create URL.
    ncr_url = NCR_SOAP_SERVICE_NOW_UPDATE_URL or secret.get("uk-snowfall-ncr-servicenow-update-url")
    if not ncr_url:
        ncr_url = secret.get("uk-snowfall-ncr-servicenow-resolve-url")
    if not ncr_url:
        create_url = secret.get("uk-snowfall-ncr-servicenow-url", "")
        ncr_url = create_url.replace("CreateServiceRequest", "UpdateServiceRequest")

    username = secret.get("uk-snowfall-ncr-servicenow-username")
    password = secret.get("uk-snowfall-ncr-servicenow-password")

    if not ncr_url or not username or not password:
        raise RuntimeError(
            f"Secret '{SECRET_NAME}' missing required keys for close Lambda. "
            "Need uk-snowfall-ncr-servicenow-update-url (or -resolve-url/-url), -username, -password."
        )

    _NCR_CREDS = (ncr_url, username, password)
    return _NCR_CREDS


def _post_to_ncr(payload: dict) -> dict:
    ncr_url, ncr_username, ncr_password = _get_ncr_credentials()

    body = json.dumps(payload).encode("utf-8")
    credentials = base64.b64encode(f"{ncr_username}:{ncr_password}".encode()).decode()

    request = urllib.request.Request(ncr_url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    request.add_header("Authorization", f"Basic {credentials}")
    request.add_header("Content-Length", str(len(body)))

    if VERIFY_SSL:
        ssl_ctx = ssl.create_default_context()
    else:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(request, context=ssl_ctx, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
            print(f"NCR HTTP status: {resp.status}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"NCR HTTP error {exc.code}: {raw[:500]}")
    except urllib.error.URLError as exc:
        print(f"NCR connection error: {exc.reason}")
        return {
            "Header": {
                "Status": "ERROR",
                "Fault": {"FaultCode": "CONNECTION_ERROR", "FaultDescription": str(exc.reason)},
            },
        }

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "Header": {
                "Status": "ERROR",
                "Fault": {"FaultCode": "INVALID_JSON", "FaultDescription": raw[:500]},
            },
            "_raw": raw[:2000],
        }


# ---------------------------------------------------------------------------
# DynamoDB updates
# ---------------------------------------------------------------------------

def _update_ticket_resolved(ncr_ticket_id: str, ncr_status: str, fault_description):
    """Update the SERVICE_NOW_TICKETS_TABLE row (keyed by NCR#<id>) with resolve result."""
    ticket_id = f"NCR#{ncr_ticket_id}"
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        tickets_table.update_item(
            Key={"ticket_id": ticket_id},
            UpdateExpression=(
                "SET resolved_at = :ts, ncr_close_status = :cs, close_notes = :cn"
            ),
            ExpressionAttributeValues={
                ":ts": now_iso,
                ":cs": ncr_status,
                ":cn": fault_description or RESOLUTION_TEXT,
            },
        )
        print(f"Updated ticket row {ticket_id} → resolved_at set (ncr_status={ncr_status})")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to update ticket row {ticket_id}: {exc}")


def _mark_case_closed(case_id: str, ncr_ticket_id, ncr_status: str):
    """Update the PROACTIVE_ALERTS_TABLE case row to CLOSED."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        update_expr = "SET #s = :s, last_updated_at = :ts, ncr_close_status = :cs"
        expr_values = {
            ":s": "CLOSED",
            ":ts": now_iso,
            ":cs": ncr_status,
        }
        if ncr_ticket_id:
            update_expr += ", ncr_ticket_id = :tid"
            expr_values[":tid"] = ncr_ticket_id

        proactive_alerts_table.update_item(
            Key={"alert_id": case_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=expr_values,
        )
        print(f"Case {case_id} marked CLOSED (ncr_status={ncr_status})")
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to mark case {case_id} as CLOSED: {exc}")
