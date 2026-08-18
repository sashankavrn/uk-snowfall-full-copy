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
    SECRET_NAME                (optional) AWS Secrets Manager secret holding NCR creds.
                                  Defaults to "uk-snowfall-ncr-servicenow". The secret
                                  JSON must contain keys:
                                    uk-snowfall-ncr-servicenow-url,
                                    uk-snowfall-ncr-servicenow-username,
                                    uk-snowfall-ncr-servicenow-password.
    SECRET_REGION              (optional) defaults to "eu-central-1".
    SERVICE_NOW_TICKETS_TABLE  e.g. uk-snowfall-dev-service-now-tickets
    RULES_TABLE                e.g. uk-snowfall-dev-incident-rules
    SOURCE_SYSTEM              (optional) defaults to "WS"
    USER_ID                    (optional) defaults to "UKMCD"
    COUNTRY_CODE               (optional) defaults to "UK"
    NCR_SOAP_SERVICE_NOW_CREATE_URL  (optional) direct CreateServiceRequest URL override
    NCR_VERIFY_SSL             (optional) "true"/"false" - defaults to "false"
                                  (NCR CERT uses a private CA)
    NCR_REQUEST_TIMEOUT_SECONDS (optional) defaults to "60". Increase if NCR
                                  endpoint responses are slow.
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

SECRET_NAME = os.environ.get("SECRET_NAME", "uk-snowfall-ncr-servicenow")
SECRET_REGION = os.environ.get("SECRET_REGION", "eu-central-1")

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
RULES_TABLE = os.environ["RULES_TABLE"]

SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "WS")
USER_ID = os.environ.get("USER_ID", "UKMCD")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "UK")
NCR_SOAP_SERVICE_NOW_CREATE_URL = os.environ.get("NCR_SOAP_SERVICE_NOW_CREATE_URL", "").strip()
VERIFY_SSL = os.environ.get("NCR_VERIFY_SSL", "false").lower() == "true"

REQUEST_TIMEOUT_SECONDS = 50

# Cached NCR credentials (populated on first call)
_NCR_CREDS = None


def _get_ncr_credentials():
    """Fetch NCR URL, username and password from AWS Secrets Manager.
    Cached for the life of the Lambda container."""
    global _NCR_CREDS
    if _NCR_CREDS is not None:
        return _NCR_CREDS

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=SECRET_REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])

    url = (
        NCR_SOAP_SERVICE_NOW_CREATE_URL
        or secret.get("uk-snowfall-ncr-servicenow-create-url")
        or secret.get("uk-snowfall-ncr-servicenow-url")
    )
    username = secret.get("uk-snowfall-ncr-servicenow-username")
    password = secret.get("uk-snowfall-ncr-servicenow-password")

    if not url or not username or not password:
        raise RuntimeError(
            f"Secret '{SECRET_NAME}' missing one of: "
            "uk-snowfall-ncr-servicenow-create-url (or uk-snowfall-ncr-servicenow-url), "
            "uk-snowfall-ncr-servicenow-username, "
            "uk-snowfall-ncr-servicenow-password"
        )

    _NCR_CREDS = (url, username, password)
    return _NCR_CREDS

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
    print("NCR mapping validation (BEGIN)")
    print(json.dumps(_build_mapping_validation_rows(payload, alert, rule or {}), default=str, indent=2))
    print("NCR mapping validation (END)")
    print("NCR rule field mapping reference (BEGIN)")
    print(json.dumps(_build_rule_field_mapping_reference(), default=str, indent=2))
    print("NCR rule field mapping reference (END)")

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

    raw_message = alert.get("message", "")
    if isinstance(raw_message, str):
        message = raw_message.strip()
    elif isinstance(raw_message, (int, float, bool)):
        message = str(raw_message).strip()
    else:
        message = ""
    short_description = (
        str(rule.get("servicenow_short_description") or rule.get("short_description") or rule.get("incident_description") or message)
        .splitlines()[0][:160]
        or "Snowfall proactive alert"
    )
    # SF-752: NCR Description must come from the SQL-returned alert message,
    # with Summary as fallback if message is missing/unusable.
    description_text = message or short_description

    raw_ticket_id = str(alert.get("alert_id") or f"SNOWFALL{uuid.uuid4().hex}")
    # NCR's working Postman sample uses a short alphanumeric CustomerTicketID (e.g. "219911").
    # NCR has rejected long values containing '#' / '-' with a generic 500.
    # Strip non-alphanumerics and cap to 32 chars to match the known-good shape.
    customer_ticket_id = "".join(ch for ch in raw_ticket_id if ch.isalnum())[:32] or "SNOWFALL"
    site_number = str(alert.get("restaurant_number") or "").strip()
    # NCR expects UK restaurant numbers zero-padded to exactly 4 digits (e.g. 59 -> "0059").
    # Strip leading zeros first so over-padded values like "04071" become "4071".
    if site_number.isdigit():
        site_number = str(int(site_number)).zfill(4)

    rule_category = rule.get("servicenow_category") or rule.get("category")
    rule_subcategory = (
        rule.get("servicenow_subcategory")
        or rule.get("subcategory")
        or rule.get("servicenow_Subcategory")
    )
    rule_business_service = (
        rule.get("servicenow_business_service")
        or rule.get("business_service")
        or rule.get("BusinessService")
    )
    rule_service_offering = (
        rule.get("servicenow_service_offering")
        or rule.get("service_offering")
        or rule.get("ServiceOffering")
    )
    rule_request_type = (
        rule.get("servicenow_request_type")
        or rule.get("request_type")
        or rule_category
        or "Software"
    )
    rule_priority = rule.get("servicenow_priority") or rule.get("priority")

    # Field order intentionally matches the known-good NCR Postman sample as closely as possible.
    create_request = {
        "CountryCode": _resolve_country_code(alert.get("restaurant_number", "")),
        "CustomerTicketID": customer_ticket_id,
        "RequestType": str(rule_request_type),
        "Priority": _coerce_int(rule_priority, default=3),
        "Summary": short_description,
        "Description": description_text,
        "Category": str(rule_category or "Software"),
    }
    if rule_subcategory:
        create_request["Subcategory"] = str(rule_subcategory)
    if rule_business_service:
        create_request["BusinessService"] = str(rule_business_service)
    if rule_service_offering:
        create_request["ServiceOffering"] = str(rule_service_offering)
    create_request["Caller"] = _build_caller(rule)
    create_request["Site"] = {"SiteNumber": site_number}
    create_request["Remark"] = {
        "Text": f"Auto-created from Snowfall proactive alert {customer_ticket_id}"
    }

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


def _build_mapping_validation_rows(payload: dict, alert: dict, rule: dict) -> list[dict]:
    create_req = payload.get("CreateServiceRequest", {}) or {}
    payload_caller = create_req.get("Caller", {}) or {}

    def _str_or_empty(value):
        return "" if value is None else str(value)

    def _as_candidates(keys):
        out = []
        for key in keys:
            value = rule.get(key)
            if value not in (None, ""):
                out.append({"key": key, "value": value})
        return out

    def _status(payload_value, candidates):
        payload_norm = _str_or_empty(payload_value).strip().lower()
        if not candidates:
            return "NO_RULE_VALUE"
        for item in candidates:
            if payload_norm == _str_or_empty(item["value"]).strip().lower():
                return "MATCH"
        return "MISMATCH"

    rows = []

    rows.append(
        {
            "field": "Category",
            "payload_value": create_req.get("Category"),
            "rule_candidates": _as_candidates(["servicenow_category", "category"]),
        }
    )
    rows.append(
        {
            "field": "Subcategory",
            "payload_value": create_req.get("Subcategory"),
            "rule_candidates": _as_candidates(["servicenow_subcategory", "subcategory", "servicenow_Subcategory"]),
        }
    )
    rows.append(
        {
            "field": "BusinessService",
            "payload_value": create_req.get("BusinessService"),
            "rule_candidates": _as_candidates(["servicenow_business_service", "business_service", "BusinessService"]),
        }
    )
    rows.append(
        {
            "field": "ServiceOffering",
            "payload_value": create_req.get("ServiceOffering"),
            "rule_candidates": _as_candidates(["servicenow_service_offering", "service_offering", "ServiceOffering"]),
        }
    )
    rows.append(
        {
            "field": "RequestType",
            "payload_value": create_req.get("RequestType"),
            "rule_candidates": _as_candidates(["servicenow_request_type", "request_type", "servicenow_category", "category"]),
        }
    )
    rows.append(
        {
            "field": "Priority",
            "payload_value": create_req.get("Priority"),
            "rule_candidates": _as_candidates(["servicenow_priority", "priority"]),
        }
    )
    rows.append(
        {
            "field": "Summary",
            "payload_value": create_req.get("Summary"),
            "rule_candidates": _as_candidates(["servicenow_short_description", "short_description", "incident_description"]),
        }
    )
    rows.append(
        {
            "field": "Description",
            "payload_value": create_req.get("Description"),
            "rule_candidates": (
                [{"key": "alert.message", "value": alert.get("message")}]
                if alert.get("message") not in (None, "")
                else [{"key": "CreateServiceRequest.Summary", "value": create_req.get("Summary")}]
            ),
        }
    )
    rows.append(
        {
            "field": "Caller.FirstName",
            "payload_value": payload_caller.get("FirstName"),
            "rule_candidates": _as_candidates(["caller_first_name"]),
        }
    )
    rows.append(
        {
            "field": "Caller.LastName",
            "payload_value": payload_caller.get("LastName"),
            "rule_candidates": _as_candidates(["caller_last_name"]),
        }
    )
    rows.append(
        {
            "field": "Caller.EmailAddress",
            "payload_value": payload_caller.get("EmailAddress"),
            "rule_candidates": _as_candidates(["caller_email"]),
        }
    )

    for row in rows:
        row["status"] = _status(row.get("payload_value"), row.get("rule_candidates") or [])

    rows.append(
        {
            "field": "CustomerTicketID",
            "payload_value": create_req.get("CustomerTicketID"),
            "derived_from": "alert.alert_id",
            "alert_value": alert.get("alert_id"),
            "status": "DERIVED",
        }
    )
    rows.append(
        {
            "field": "Site.SiteNumber",
            "payload_value": (create_req.get("Site") or {}).get("SiteNumber"),
            "derived_from": "alert.restaurant_number (zero-padded)",
            "alert_value": alert.get("restaurant_number"),
            "status": "DERIVED",
        }
    )

    return rows


def _build_rule_field_mapping_reference() -> list[dict]:
    """Reference table for rule authors: preferred key + accepted aliases.

    This is log-only guidance and does not change payload behavior.
    """
    return [
        {
            "payload_field": "CreateServiceRequest.Category",
            "preferred_rule_key": "servicenow_category",
            "accepted_aliases": ["category"],
            "notes": "Used directly for Category and as RequestType fallback.",
        },
        {
            "payload_field": "CreateServiceRequest.Subcategory",
            "preferred_rule_key": "servicenow_subcategory",
            "accepted_aliases": ["subcategory", "servicenow_Subcategory"],
            "notes": "Only included when value is present.",
        },
        {
            "payload_field": "CreateServiceRequest.BusinessService",
            "preferred_rule_key": "servicenow_business_service",
            "accepted_aliases": ["business_service", "BusinessService"],
            "notes": "Only included when value is present.",
        },
        {
            "payload_field": "CreateServiceRequest.ServiceOffering",
            "preferred_rule_key": "servicenow_service_offering",
            "accepted_aliases": ["service_offering", "ServiceOffering"],
            "notes": "Only included when value is present.",
        },
        {
            "payload_field": "CreateServiceRequest.RequestType",
            "preferred_rule_key": "servicenow_request_type",
            "accepted_aliases": ["request_type"],
            "notes": "Fallback order: servicenow_request_type -> request_type -> servicenow_category/category -> 'Software'.",
        },
        {
            "payload_field": "CreateServiceRequest.Priority",
            "preferred_rule_key": "servicenow_priority",
            "accepted_aliases": ["priority"],
            "notes": "Defaults to 3 when empty/invalid.",
        },
        {
            "payload_field": "CreateServiceRequest.Summary",
            "preferred_rule_key": "servicenow_short_description",
            "accepted_aliases": ["short_description", "incident_description"],
            "notes": "Fallback order: servicenow_short_description -> short_description -> incident_description -> alert message first line.",
        },
        {
            "payload_field": "CreateServiceRequest.Description",
            "preferred_rule_key": "alert.message",
            "accepted_aliases": [],
            "notes": "Fallback order: alert.message -> Summary.",
        },
        {
            "payload_field": "CreateServiceRequest.Caller.FirstName",
            "preferred_rule_key": "caller_first_name",
            "accepted_aliases": ["caller.first_name"],
            "notes": "Default 'Snowfall'.",
        },
        {
            "payload_field": "CreateServiceRequest.Caller.LastName",
            "preferred_rule_key": "caller_last_name",
            "accepted_aliases": ["caller.last_name"],
            "notes": "Default 'Alerts'.",
        },
        {
            "payload_field": "CreateServiceRequest.Caller.EmailAddress",
            "preferred_rule_key": "caller_email",
            "accepted_aliases": ["caller.email"],
            "notes": "Default snowfall-proactive-alerts mailbox.",
        },
    ]


# ---------------------------------------------------------------------------
# NCR HTTP call
# ---------------------------------------------------------------------------

def _post_to_ncr(payload: dict) -> dict:
    ncr_url, ncr_username, ncr_password = _get_ncr_credentials()

    body = json.dumps(payload).encode("utf-8")
    credentials = base64.b64encode(f"{ncr_username}:{ncr_password}".encode()).decode()

    request = urllib.request.Request(ncr_url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "*/*")
    request.add_header("Accept-Encoding", "identity")
    request.add_header("Connection", "keep-alive")
    # NCR's F5 BIG-IP front end can filter requests with the default
    # "Python-urllib/3.x" user agent. Mimic the Postman/`requests` UA that
    # is known to succeed against the same endpoint.
    request.add_header("User-Agent", "PostmanRuntime/7.39.0")
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
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "Header": {
                "Status": "ERROR",
                "Fault": {"FaultCode": "INVALID_JSON", "FaultDescription": raw[:500]},
            },
            "NCRIncidentUpdate": {"NCRTicketID": None},
            "_raw": raw[:2000],
        }

    return parsed


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

    create_req = payload.get("CreateServiceRequest", {}) or {}
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
        "service_offering": str(
            create_req.get("ServiceOffering")
            or rule.get("service_offering")
            or rule.get("servicenow_service_offering")
            or ""
        ),
        "category": str(
            create_req.get("Category")
            or rule.get("category")
            or rule.get("servicenow_category")
            or ""
        ),
        "subcategory": str(
            create_req.get("Subcategory")
            or rule.get("subcategory")
            or rule.get("servicenow_subcategory")
            or rule.get("servicenow_Subcategory")
            or ""
        ),
        "priority": str(
            create_req.get("Priority")
            or rule.get("servicenow_priority")
            or rule.get("priority")
            or ""
        ),
        "request_type": str(create_req.get("RequestType") or rule.get("request_type") or ""),
        "country_code": str(create_req.get("CountryCode") or ""),
        "site_number": str((create_req.get("Site") or {}).get("SiteNumber") or ""),
        "customer_ticket_id": str(create_req.get("CustomerTicketID") or ""),
        "summary": str(create_req.get("Summary") or ""),
        "description": str(create_req.get("Description") or ""),
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


def _resolve_country_code(restaurant_number) -> str:
    """Return the CountryCode for the NCR payload.

    Restaurants with numbers >= 7000 are Ireland (IE) sites.
    All others use the COUNTRY_CODE env var (default 'UK').
    """
    try:
        if restaurant_number is not None and str(restaurant_number).strip().isdigit():
            if int(str(restaurant_number).strip()) >= 7000:
                return "IE"
    except (TypeError, ValueError):
        pass
    return COUNTRY_CODE


def _coerce_int(value, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default
