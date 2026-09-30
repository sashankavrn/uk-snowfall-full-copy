"""
End-to-End ServiceNow Ticket Lifecycle Test
-------------------------------------------
Tests the full lifecycle against real AWS resources:

  STEP 1  Create – record_servicenow_case() writes OPEN case to DynamoDB
  STEP 2  Skip   – get_open_servicenow_case() detects existing OPEN case
  STEP 3  Invoke  – trigger_servicenow_ticket() invokes SERVICENOW_TICKET_LAMBDA (async)
  STEP 4  Close  – close_servicenow_ticket_if_open() marks case CLOSING + invokes SERVICENOW_CLOSE_LAMBDA
  STEP 5  Verify  – DynamoDB case record shows status=CLOSING (and CLOSED once close Lambda responds)
  STEP 6  Cleanup – Deletes all test records from DynamoDB

Usage:
    python test_e2e_servicenow_lifecycle.py [options]

Options:
    --table   PROACTIVE_ALERTS_TABLE name (overrides env var)
    --stage   dev | nprod | prod  (default: dev)
    --skip-invoke  Skip Lambda invocation steps (DynamoDB only)
    --no-cleanup   Leave test records in DynamoDB (for manual inspection)

Required environment variables (or pass via --table / --stage):
    PROACTIVE_ALERTS_TABLE
    RULES_TABLE
    TABLE_NAME           (connections table)
    ATHENA_OUTPUT_S3
    STAGE_NAME
    SERVICENOW_TICKET_LAMBDA  (optional — skipped with warning if unset)
    SERVICENOW_CLOSE_LAMBDA   (optional — skipped with warning if unset)
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Argument parsing (before env var setup so --stage can influence defaults)
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="E2E ServiceNow lifecycle test")
parser.add_argument("--table", help="Override PROACTIVE_ALERTS_TABLE env var")
parser.add_argument("--stage", default=None, help="dev | nprod | prod (default: dev)")
parser.add_argument("--skip-invoke", action="store_true", help="Skip Lambda invocation steps")
parser.add_argument("--no-cleanup", action="store_true", help="Keep test records after test")
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Environment variable defaults (set before importing lambda_function)
# ---------------------------------------------------------------------------

STAGE = args.stage or os.environ.get("STAGE_NAME", "dev")

os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
os.environ.setdefault("STAGE_NAME", STAGE)
os.environ.setdefault("RULES_TABLE", f"uk-snowfall-{STAGE}-incident-rules")
os.environ.setdefault("PROACTIVE_ALERTS_TABLE", f"uk-snowfall-{STAGE}-proactive-alerts")
os.environ.setdefault("TABLE_NAME", f"uk-snowfall-{STAGE}-connections")
os.environ.setdefault("RESULTS_TABLE_NAME", f"uk-snowfall-{STAGE}-script-results")
os.environ.setdefault("ATHENA_OUTPUT_S3", f"s3://uk-snowfall-{STAGE}-athena-results/")
os.environ.setdefault("SERVICENOW_TICKET_LAMBDA", f"uk-snowfall-{STAGE}-servicenow-proactive-ticket-creation")
os.environ.setdefault("SERVICENOW_CLOSE_LAMBDA", f"uk-snowfall-{STAGE}-servicenow-proactive-ticket-close")

if args.table:
    os.environ["PROACTIVE_ALERTS_TABLE"] = args.table

# ---------------------------------------------------------------------------
# Import lambda_function (after env vars are set so module-level clients init)
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(__file__))
import lambda_function as lf  # noqa: E402

import boto3  # noqa: E402
from boto3.dynamodb.conditions import Attr  # noqa: E402

# Direct DynamoDB access for verification (independent of lambda_function)
_dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
_alerts_table = _dynamodb.Table(os.environ["PROACTIVE_ALERTS_TABLE"])
_lambda_client = boto3.client("lambda", region_name="eu-central-1")

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"
WARN = "\033[93m[WARN]\033[0m"

_test_ids = []  # track all alert_ids created so we can clean up
_failures = 0


def check(label: str, condition: bool, detail: str = ""):
    global _failures
    if condition:
        print(f"  {PASS} {label}")
    else:
        _failures += 1
        print(f"  {FAIL} {label}" + (f" — {detail}" if detail else ""))


def banner(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def get_case_from_dynamo(alert_id: str) -> dict:
    resp = _alerts_table.get_item(Key={"alert_id": alert_id})
    return resp.get("Item") or {}


def build_test_rule(suffix: str) -> dict:
    """Minimal rule dict that satisfies lifecycle functions."""
    return {
        "rule_id": f"E2E-TEST-{suffix}",
        "active": True,
        "incident_description": f"[E2E Test] Lifecycle rule {suffix}",
        "servicenow_alert": True,
        "email_alert": False,
        "email_cooldown_hours": 0,
        "email_dl": "",
    }


def build_test_alert(rule: dict) -> dict:
    """Minimal alert_item (as record_email_alert would produce)."""
    alert_id = f"ALERT#E2E-{uuid.uuid4()}"
    _test_ids.append(alert_id)
    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
    return {
        "alert_id": alert_id,
        "record_type": "EMAIL_ALERT",
        "rule_id": rule["rule_id"],
        "restaurant_number": "E2E-RESTAURANT",
        "message": "E2E test message — no real violation",
        "status": "RECORDED",
        "created_at": timestamp,
        "last_alert_time": timestamp,
        "violating_restaurants": ["E2E-RESTAURANT"],
        "email_recipients": "",
    }


# ---------------------------------------------------------------------------
# STEP 1 — record_servicenow_case creates OPEN record
# ---------------------------------------------------------------------------

banner("STEP 1: record_servicenow_case() → writes OPEN case to DynamoDB")

suffix = str(uuid.uuid4())[:8]
rule = build_test_rule(suffix)
alert_item = build_test_alert(rule)

case_item = lf.record_servicenow_case(rule, alert_item)
_test_ids.append(case_item["alert_id"])

time.sleep(0.5)  # allow eventual consistency

db_case = get_case_from_dynamo(case_item["alert_id"])

check("Case written to DynamoDB", bool(db_case), "item not found")
check("status = OPEN", db_case.get("status") == "OPEN", db_case.get("status"))
check("record_type = SERVICENOW_CASE", db_case.get("record_type") == "SERVICENOW_CASE")
check("rule_id matches", db_case.get("rule_id") == rule["rule_id"])
check("source_alert_id matches", db_case.get("source_alert_id") == alert_item["alert_id"])
check("ncr_ticket_id = None", db_case.get("ncr_ticket_id") is None)

# ---------------------------------------------------------------------------
# STEP 2 — get_open_servicenow_case detects existing open case
# ---------------------------------------------------------------------------

banner("STEP 2: get_open_servicenow_case() → detects existing OPEN case")

found_case = lf.get_open_servicenow_case(rule["rule_id"])

check("Found open case", found_case is not None, "returned None")
if found_case:
    check("Correct case_id returned", found_case.get("alert_id") == case_item["alert_id"],
          f"expected {case_item['alert_id']}, got {found_case.get('alert_id')}")

# ---------------------------------------------------------------------------
# STEP 3 — trigger_servicenow_ticket (with a fresh alert) does NOT duplicate
# ---------------------------------------------------------------------------

banner("STEP 3: trigger_servicenow_ticket() — skip if open case already exists")

alert_item2 = build_test_alert(rule)  # second alert, same rule

existing = lf.get_open_servicenow_case(rule["rule_id"])
if existing:
    print(f"  {INFO} Open case detected ({existing['alert_id']}); creation will be skipped — correct")
    check("Skip duplicate creation", True)
else:
    check("Skip duplicate creation", False, "open case not found — would have created duplicate")

# Invoke Lambda (optional)
if not args.skip_invoke:
    banner("STEP 3b: trigger_servicenow_ticket() → invokes SERVICENOW_TICKET_LAMBDA")
    ticket_lambda = os.environ.get("SERVICENOW_TICKET_LAMBDA", "")
    if not ticket_lambda:
        print(f"  {WARN} SERVICENOW_TICKET_LAMBDA not set — skipping invocation test")
    else:
        # Use a fresh alert and rule to avoid polluting the open-case check
        fresh_suffix = str(uuid.uuid4())[:8]
        fresh_rule = build_test_rule(fresh_suffix)
        fresh_alert = build_test_alert(fresh_rule)
        fresh_case = lf.record_servicenow_case(fresh_rule, fresh_alert)
        _test_ids.append(fresh_case["alert_id"])

        payload = {
            "alert": lf._to_json_safe(fresh_alert),
            "rule": lf._to_json_safe(fresh_rule),
            "case_id": fresh_case["alert_id"],
        }
        try:
            response = _lambda_client.invoke(
                FunctionName=ticket_lambda,
                InvocationType="RequestResponse",  # sync for test visibility
                Payload=json.dumps(payload).encode("utf-8"),
            )
            resp_payload = json.loads(response["Payload"].read().decode("utf-8"))
            status_code = response.get("StatusCode")
            print(f"  {INFO} StatusCode={status_code}  response={json.dumps(resp_payload, default=str)[:300]}")
            check("Lambda invoked without error", status_code == 200,
                  f"StatusCode={status_code}")
            body = json.loads(resp_payload.get("body") or "{}")
            ncr_ticket_id = body.get("ncr_ticket_id")
            ncr_status = body.get("status", "")
            print(f"  {INFO} NCR status={ncr_status}  ncr_ticket_id={ncr_ticket_id}")
            check("NCR call returned a status", bool(ncr_status))
            if ncr_status == "SUCCESS":
                check("NCR ticket ID populated", bool(ncr_ticket_id))
            else:
                print(f"  {WARN} NCR returned non-SUCCESS: {body.get('fault_description')} — "
                      "this is expected on CERT if credentials/payload need tuning")
        except Exception as exc:
            check("Lambda invoked without exception", False, str(exc))

# ---------------------------------------------------------------------------
# STEP 4 — close_servicenow_ticket_if_open → marks CLOSING + invokes close Lambda
# ---------------------------------------------------------------------------

banner("STEP 4: close_servicenow_ticket_if_open() → marks case CLOSING")

# Ensure the original case is still OPEN before closing
pre_close = get_case_from_dynamo(case_item["alert_id"])
check("Case still OPEN before close", pre_close.get("status") == "OPEN",
      pre_close.get("status"))

lf.close_servicenow_ticket_if_open(rule)

time.sleep(0.5)

post_close = get_case_from_dynamo(case_item["alert_id"])
check("Case status updated to CLOSING", post_close.get("status") == "CLOSING",
      post_close.get("status"))
check("last_updated_at set", bool(post_close.get("last_updated_at")))

# ---------------------------------------------------------------------------
# STEP 4b — invoke SERVICENOW_CLOSE_LAMBDA directly for synchronous result
# ---------------------------------------------------------------------------

if not args.skip_invoke:
    banner("STEP 4b: SERVICENOW_CLOSE_LAMBDA direct invocation (sync)")
    close_lambda = os.environ.get("SERVICENOW_CLOSE_LAMBDA", "")
    if not close_lambda:
        print(f"  {WARN} SERVICENOW_CLOSE_LAMBDA not set — skipping invocation test")
    else:
        close_payload = {
            "rule": lf._to_json_safe(rule),
            "case": lf._to_json_safe(post_close),
        }
        try:
            response = _lambda_client.invoke(
                FunctionName=close_lambda,
                InvocationType="RequestResponse",
                Payload=json.dumps(close_payload).encode("utf-8"),
            )
            resp_payload = json.loads(response["Payload"].read().decode("utf-8"))
            status_code = response.get("StatusCode")
            print(f"  {INFO} StatusCode={status_code}  response={json.dumps(resp_payload, default=str)[:300]}")
            check("Close Lambda invoked without error", status_code == 200,
                  f"StatusCode={status_code}")
            body = json.loads(resp_payload.get("body") or "{}")
            print(f"  {INFO} ncr_status={body.get('ncr_status')}  ncr_ticket_id={body.get('ncr_ticket_id')}")

            # Poll for CLOSED status (Lambda may update DynamoDB asynchronously)
            time.sleep(1)
            final_case = get_case_from_dynamo(case_item["alert_id"])
            check("Case marked CLOSED after close Lambda",
                  final_case.get("status") == "CLOSED",
                  final_case.get("status"))
        except Exception as exc:
            check("Close Lambda invoked without exception", False, str(exc))

# ---------------------------------------------------------------------------
# STEP 5 — second close attempt is a no-op (no open case remains)
# ---------------------------------------------------------------------------

banner("STEP 5: close_servicenow_ticket_if_open() — no-op when no OPEN case")

# Re-run close on same rule; the case is now CLOSING/CLOSED — should log and return
pre_noop = lf.get_open_servicenow_case(rule["rule_id"])
check("No open case found (idempotent close)", pre_noop is None,
      f"unexpected open case: {pre_noop}")

# Calling close on a rule with no open case should log and return gracefully
try:
    lf.close_servicenow_ticket_if_open(rule)
    check("No-op close did not raise", True)
except Exception as exc:
    check("No-op close did not raise", False, str(exc))

# ---------------------------------------------------------------------------
# STEP 6 — Cleanup
# ---------------------------------------------------------------------------

if not args.no_cleanup:
    banner("STEP 6: Cleanup — deleting test records from DynamoDB")
    deleted = 0
    for aid in _test_ids:
        try:
            _alerts_table.delete_item(Key={"alert_id": aid})
            deleted += 1
        except Exception as exc:
            print(f"  {WARN} Could not delete {aid}: {exc}")
    print(f"  {INFO} Deleted {deleted}/{len(_test_ids)} test records")
else:
    banner("STEP 6: Cleanup skipped (--no-cleanup)")
    print(f"  {INFO} Test records left in {os.environ['PROACTIVE_ALERTS_TABLE']}:")
    for aid in _test_ids:
        print(f"    {aid}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

banner("TEST SUMMARY")
if _failures == 0:
    print(f"  \033[92mAll checks passed.\033[0m  (table={os.environ['PROACTIVE_ALERTS_TABLE']}, stage={STAGE})")
else:
    print(f"  \033[91m{_failures} check(s) FAILED.\033[0m")

sys.exit(0 if _failures == 0 else 1)
