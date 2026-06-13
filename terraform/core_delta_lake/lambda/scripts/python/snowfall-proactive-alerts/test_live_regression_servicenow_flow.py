"""
Live Regression Check: Proactive Alerts -> ServiceNow Case Flow

Purpose:
- Validate core ServiceNow case lifecycle behavior in dev/nprod/prod using real AWS resources.
- Catch regressions before pushing feature changes.

Default behavior is safe:
- Creates only temporary test case rows in PROACTIVE_ALERTS_TABLE.
- Does NOT call NCR/ServiceNow by default.
- Cleans up created rows unless --no-cleanup is used.

Usage:
  python test_live_regression_servicenow_flow.py --stage dev
  python test_live_regression_servicenow_flow.py --stage dev --invoke-close-lambda
  python test_live_regression_servicenow_flow.py --stage dev --no-cleanup
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    import boto3
except ModuleNotFoundError:
    print("[ERROR] Missing dependency: boto3")
    print("Install it with: python -m pip install boto3")
    raise SystemExit(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live regression for proactive ServiceNow flow")
    parser.add_argument("--stage", default=os.environ.get("STAGE_NAME", "dev"), help="dev | nprod | prod")
    parser.add_argument(
        "--invoke-close-lambda",
        action="store_true",
        help="Invoke close lambda synchronously (hits NCR path; use only when intended)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temporary DynamoDB test rows for inspection",
    )
    return parser.parse_args()


def set_env_defaults(stage: str) -> None:
    os.environ.setdefault("AWS_DEFAULT_REGION", "eu-central-1")
    os.environ.setdefault("STAGE_NAME", stage)
    os.environ.setdefault("RULES_TABLE", f"uk-snowfall-{stage}-incident-rules")
    os.environ.setdefault("PROACTIVE_ALERTS_TABLE", f"uk-snowfall-{stage}-proactive-alerts")
    os.environ.setdefault("TABLE_NAME", f"uk-snowfall-{stage}-connections")
    os.environ.setdefault("RESULTS_TABLE_NAME", f"uk-snowfall-{stage}-script-results")
    os.environ.setdefault("ATHENA_OUTPUT_S3", f"s3://uk-snowfall-{stage}-athena-results/")
    os.environ.setdefault("SERVICENOW_TICKET_LAMBDA", f"uk-snowfall-{stage}-servicenow-proactive-ticket-creation")
    os.environ.setdefault("SERVICENOW_CLOSE_LAMBDA", f"uk-snowfall-{stage}-servicenow-proactive-ticket-close")


PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
WARN = "[WARN]"


def banner(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(title)
    print(f"{'=' * 70}")


def run() -> int:
    args = parse_args()
    set_env_defaults(args.stage)

    region = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")

    # Fail fast with actionable guidance if local AWS credentials are expired.
    sts_client = boto3.client("sts", region_name=region)
    try:
        ident = sts_client.get_caller_identity()
        print(f"{INFO} AWS identity: {ident.get('Arn')}")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "ExpiredToken" in msg or "expired" in msg.lower():
            print("[ERROR] AWS credentials are expired.")
            print("Refresh your AWS session (SSO/login/assume-role) and rerun.")
            return 3
        print(f"[ERROR] Unable to validate AWS credentials: {exc}")
        return 3

    # Import after env vars are set so module-level table clients initialize correctly.
    script_dir = os.path.dirname(__file__)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    import lambda_function as lf  # noqa: E402

    dynamodb = boto3.resource("dynamodb", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)

    alerts_table_name = os.environ["PROACTIVE_ALERTS_TABLE"]
    alerts_table = dynamodb.Table(alerts_table_name)

    failures = 0
    created_ids: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        if condition:
            print(f"  {PASS} {label}")
        else:
            failures += 1
            suffix = f" -- {detail}" if detail else ""
            print(f"  {FAIL} {label}{suffix}")

    def get_item(alert_id: str) -> dict:
        resp = alerts_table.get_item(Key={"alert_id": alert_id})
        return resp.get("Item") or {}

    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    test_rule = {
        "rule_id": f"REG-{suffix}",
        "active": True,
        "incident_description": f"[Regression] Rule {suffix}",
        "servicenow_alert": True,
        "email_alert": False,
        "email_cooldown_hours": 0,
        "email_dl": "",
    }

    test_alert = {
        "alert_id": f"ALERT#REG-{suffix}",
        "record_type": "EMAIL_ALERT",
        "rule_id": test_rule["rule_id"],
        "restaurant_number": "04071",
        "message": "Regression test synthetic alert",
        "status": "RECORDED",
        "created_at": now,
        "last_alert_time": now,
        "violating_restaurants": ["04071"],
        "email_recipients": "",
    }

    created_ids.append(test_alert["alert_id"])

    banner("STEP 1: Create ServiceNow case row")
    case_item = lf.record_servicenow_case(test_rule, test_alert)
    case_id = case_item["alert_id"]
    created_ids.append(case_id)

    time.sleep(0.5)
    db_case = get_item(case_id)

    check("Case row created", bool(db_case), "item not found")
    check("record_type is SERVICENOW_CASE", db_case.get("record_type") == "SERVICENOW_CASE")
    check("status is OPEN", db_case.get("status") == "OPEN", str(db_case.get("status")))

    banner("STEP 2: Detect open case")
    open_case = lf.get_open_servicenow_case(test_rule["rule_id"])
    check("Open case lookup returns case", open_case is not None)
    if open_case:
        check("Open case id matches", open_case.get("alert_id") == case_id)

    banner("STEP 3: Mark case CLOSING via close helper")
    lf.close_servicenow_ticket_if_open(test_rule)
    time.sleep(0.5)

    db_case_after_close_request = get_item(case_id)
    check(
        "Status changed to CLOSING",
        db_case_after_close_request.get("status") == "CLOSING",
        str(db_case_after_close_request.get("status")),
    )

    if args.invoke_close_lambda:
        banner("STEP 4: Optional sync invoke of close lambda")
        close_lambda_name = os.environ.get("SERVICENOW_CLOSE_LAMBDA", "")
        if not close_lambda_name:
            print(f"  {WARN} SERVICENOW_CLOSE_LAMBDA is not configured")
            failures += 1
        else:
            payload = {
                "rule": lf._to_json_safe(test_rule),
                "case": lf._to_json_safe(db_case_after_close_request),
            }
            try:
                response = lambda_client.invoke(
                    FunctionName=close_lambda_name,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(payload).encode("utf-8"),
                )
                status_code = response.get("StatusCode")
                raw_payload = response["Payload"].read().decode("utf-8")
                print(f"  {INFO} Lambda StatusCode={status_code}")
                print(f"  {INFO} Lambda response={raw_payload[:500]}")
                check("Close lambda invoked", status_code == 200, str(status_code))
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  {FAIL} Close lambda invocation failed -- {exc}")

    banner("STEP 5: No-open-case safety check")
    try:
        lf.close_servicenow_ticket_if_open({"rule_id": f"MISSING-{suffix}"})
        check("No-open-case call does not crash", True)
    except Exception as exc:  # noqa: BLE001
        check("No-open-case call does not crash", False, str(exc))

    if args.no_cleanup:
        banner("CLEANUP SKIPPED")
        print(f"  {INFO} Left test rows in {alerts_table_name}")
        for item_id in created_ids:
            print(f"  {INFO} {item_id}")
    else:
        banner("CLEANUP")
        deleted = 0
        for item_id in created_ids:
            try:
                alerts_table.delete_item(Key={"alert_id": item_id})
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  {WARN} Failed to delete {item_id}: {exc}")
        print(f"  {INFO} Deleted {deleted}/{len(created_ids)} items")

    banner("SUMMARY")
    if failures == 0:
        print(f"{PASS} Live regression checks passed")
        return 0

    print(f"{FAIL} Live regression checks failed: {failures}")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
