"""
NCR Voyix - Create ServiceNow Ticket Lambda
-------------------------------------------
Invoked synchronously / asynchronously by the snowfall-proactive-alerts
Lambda for a single proactive alert that requires a ServiceNow ticket.

For that one alert this Lambda:
  1. Reads the alert payload (alert_id, rule_id, restaurant_number, message).
  2. Uses the rule data passed in by the caller, or falls back to looking
     it up in `uk-snowfall-<env>-incident-rules` if only `rule_id` is
     provided. Rule supplies service_offering, category, subcategory,
     priority and short description.
  3. POSTs a REST JSON `CreateServiceRequest` payload to NCR's CSDI
     endpoint using HTTP Basic Auth.
  4. Writes the ticket details (incl. NCRTicketID) to
     `uk-snowfall-<env>-service-now-tickets`.
  5. Returns the NCR response + persisted ticket_id to the caller.

Expected invocation event shape (either form is accepted):
    {
      "alert": { ...proactive alert row... },
      "rule":  { ...incident rule row (optional)... }
    }
  -- or simply the alert dict itself, e.g. --
    {
      "alert_id": "ALERT#...",
      "rule_id": "10",
      "restaurant_number": "4071",
      "message": "..."
    }

Environment variables (all required unless noted):
    NCR_URL                    Full NCR CreateServiceRequest endpoint URL.
    NCR_USERNAME               Basic Auth username (move to Secrets Manager in prod).
    NCR_PASSWORD               Basic Auth password (move to Secrets Manager in prod).
    SERVICE_NOW_TICKETS_TABLE  e.g. uk-snowfall-dev-service-now-tickets
    RULES_TABLE                e.g. uk-snowfall-dev-incident-rules
    SOURCE_SYSTEM              (optional) defaults to "WS"
    USER_ID                    (optional) defaults to "UKMCD"
    COUNTRY_CODE               (optional) defaults to "UK"
    NCR_VERIFY_SSL             (optional) "true"/"false" - defaults to "false"
                                  (NCR CERT uses a private CA)
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NCR_URL = os.environ["NCR_URL"]
NCR_USERNAME = os.environ["NCR_USERNAME"]
NCR_PASSWORD = os.environ["NCR_PASSWORD"]

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
RULES_TABLE = os.environ["RULES_TABLE"]

SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "WS")
USER_ID = os.environ.get("USER_ID", "UKMCD")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "UK")
VERIFY_SSL = os.environ.get("NCR_VERIFY_SSL", "false").lower() == "true"

REQUEST_TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# AWS clients
# ---------------------------------------------------------------------------

dynamodb = boto3.resource("dynamodb")
tickets_table = dynamodb.Table(SERVICE_NOW_TICKETS_TABLE)
rules_table = dynamodb.Table(RULES_TABLE)


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """Create one ServiceNow ticket for the alert payload passed in by the
    proactive-alerts Lambda."""
    print(f"Received event: {json.dumps(event, default=str)}")

    alert, rule = _extract_alert_and_rule(event)
    if not alert:
        print("[ERROR] No alert payload found in event; nothing to do.")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "missing 'alert' payload in event"}),
        }

    alert_id = alert.get("alert_id", "UNKNOWN")
    rule_id = alert.get("rule_id")
    restaurant_number = alert.get("restaurant_number", "")
    print(f"Processing alert {alert_id} (rule={rule_id}, restaurant={restaurant_number})")

    if not rule and rule_id:
        rule = _get_rule(rule_id)

    payload = _build_payload(alert, rule or {})
    print(f"NCR request payload: {json.dumps(payload)}")

    response = _post_to_ncr(payload)
    print(f"NCR response: {json.dumps(response)}")

    header = response.get("Header", {}) or {}
    status = (header.get("Status") or "").upper()
    ncr_ticket_id = (response.get("NCRIncidentUpdate") or {}).get("NCRTicketID")
    fault = header.get("Fault") or {}

    ticket_id = _save_ticket(
        alert=alert,
        rule=rule or {},
        payload=payload,
        response=response,
        status=status,
        ncr_ticket_id=ncr_ticket_id,
        fault_description=fault.get("FaultDescription"),
        fault_code=fault.get("FaultCode"),
    )

    success = status == "SUCCESS" and bool(ncr_ticket_id)
    return {
        "statusCode": 200 if success else 502,
        "body": json.dumps(
            {
                "success": success,
                "ticket_id": ticket_id,
                "ncr_ticket_id": ncr_ticket_id,
                "status": status,
                "fault_code": fault.get("FaultCode"),
                "fault_description": fault.get("FaultDescription"),
            }
        ),
    }


def _extract_alert_and_rule(event):
    """Accept either {alert: {...}, rule: {...}} or the bare alert dict."""
    if not isinstance(event, dict):
        return None, None
    if "alert" in event and isinstance(event["alert"], dict):
        rule = event.get("rule") if isinstance(event.get("rule"), dict) else None
        return event["alert"], rule
    if "alert_id" in event or "rule_id" in event:
        return event, None
    return None, None


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------

def _build_payload(alert: dict, rule: dict) -> dict:
    """Build the NCR CreateServiceRequest JSON payload from the alert + rule."""
    transaction_id = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    message = str(alert.get("message", "") or "")
    short_description = (
        str(rule.get("short_description") or rule.get("incident_description") or message)
        .splitlines()[0][:160]
        or "Snowfall proactive alert"
    )

    customer_ticket_id = str(alert.get("alert_id") or f"SNOWFALL-{uuid.uuid4()}")
    site_number = str(alert.get("restaurant_number") or "").strip()

    create_request = {
        "CountryCode": COUNTRY_CODE,
        "CustomerTicketID": customer_ticket_id,
        "RequestType": str(rule.get("request_type") or rule.get("category") or "Software"),
        "Priority": _coerce_int(rule.get("priority"), default=3),
        "Summary": short_description,
        "Description": message or short_description,
        "Category": str(rule.get("category") or "Software"),
        "Caller": _build_caller(rule),
        "Site": {"SiteNumber": site_number},
        "Remark": {"Text": f"Auto-created from Snowfall proactive alert {customer_ticket_id}"},
    }

    subcategory = rule.get("subcategory")
    if subcategory:
        create_request["Subcategory"] = str(subcategory)

    service_offering = rule.get("service_offering")
    if service_offering:
        create_request["ServiceOffering"] = str(service_offering)

    return {
        "Header": {
            "TransactionID": transaction_id,
            "USERID": USER_ID,
            "SourceSystem": SOURCE_SYSTEM,
            "TimeStamp": timestamp,
        },
        "CreateServiceRequest": create_request,
    }


def _build_caller(rule: dict) -> dict:
    caller = rule.get("caller") or {}
    return {
        "FirstName": str(caller.get("first_name") or rule.get("caller_first_name") or "Snowfall"),
        "LastName": str(caller.get("last_name") or rule.get("caller_last_name") or "Alerts"),
        "PhoneNumber": str(caller.get("phone_number") or rule.get("caller_phone") or ""),
        "EmailAddress": str(
            caller.get("email")
            or rule.get("caller_email")
            or "snowfall-proactive-alerts@ext.mcdonalds.com"
        ),
    }


# ---------------------------------------------------------------------------
# NCR HTTP call
# ---------------------------------------------------------------------------

def _post_to_ncr(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    credentials = base64.b64encode(f"{NCR_USERNAME}:{NCR_PASSWORD}".encode()).decode()

    request = urllib.request.Request(NCR_URL, data=body, method="POST")
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
            "NCRIncidentUpdate": {"NCRTicketID": None},
        }

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "Header": {
                "Status": "ERROR",
                "Fault": {"FaultCode": "INVALID_JSON", "FaultDescription": raw[:500]},
            },
            "NCRIncidentUpdate": {"NCRTicketID": None},
            "_raw": raw[:2000],
        }


# ---------------------------------------------------------------------------
# DynamoDB persistence
# ---------------------------------------------------------------------------

def _save_ticket(
    alert: dict,
    rule: dict,
    payload: dict,
    response: dict,
    status: str,
    ncr_ticket_id,
    fault_description,
    fault_code,
) -> str:
    now_iso = datetime.now(timezone.utc).isoformat()
    alert_id = alert.get("alert_id", "UNKNOWN")
    ticket_id = (
        f"NCR#{ncr_ticket_id}" if ncr_ticket_id else f"FAILED#{alert_id}#{uuid.uuid4()}"
    )

    item = {
        "ticket_id": ticket_id,
        "record_type": "SERVICENOW_TICKET",
        "alert_id": alert_id,
        "rule_id": str(alert.get("rule_id", "")),
        "restaurant_number": str(alert.get("restaurant_number", "")),
        "message": str(alert.get("message", "")),
        "status": status or "UNKNOWN",
        "ncr_ticket_id": str(ncr_ticket_id) if ncr_ticket_id else "",
        "ncr_transaction_id": payload.get("Header", {}).get("TransactionID", ""),
        "service_offering": str(rule.get("service_offering", "") or ""),
        "category": str(rule.get("category", "") or ""),
        "subcategory": str(rule.get("subcategory", "") or ""),
        "priority": str(rule.get("priority", "") or ""),
        "short_description": payload["CreateServiceRequest"]["Summary"],
        "request_payload": json.dumps(payload),
        "response_payload": json.dumps(response),
        "fault_code": str(fault_code) if fault_code else "",
        "fault_description": str(fault_description) if fault_description else "",
        "created_at": now_iso,
    }

    tickets_table.put_item(Item=item)
    print(f"Saved ticket row {ticket_id} (status={status}, ncr_ticket_id={ncr_ticket_id})")
    return ticket_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_rule(rule_id) -> dict:
    try:
        resp = rules_table.get_item(Key={"rule_id": str(rule_id)})
        rule = resp.get("Item") or {}
        if not rule:
            print(f"[WARN] No rule found for rule_id={rule_id}; using defaults")
        return rule
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Failed to fetch rule {rule_id}: {exc}; using defaults")
        return {}


def _coerce_int(value, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default
