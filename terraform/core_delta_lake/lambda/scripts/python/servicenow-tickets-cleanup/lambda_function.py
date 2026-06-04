"""
ServiceNow Tickets Cleanup Lambda (DEV utility)
-----------------------------------------------
Bulk-deletes rows from `uk-snowfall-<env>-service-now-tickets` that match
an optional `ticket_id` prefix filter (e.g. "EMAIL#", "FAILED#", "NCR#").

DEFAULT BEHAVIOR:
    - Invoking without payload deletes all rows in the table.
    - You can still use prefix/status to narrow the rows.
    - MAX_DELETE caps how many rows can be deleted per invocation.
  - Only operates on the table named in SERVICE_NOW_TICKETS_TABLE env var.

Invocation event (all fields optional):
    {
    "prefix": "EMAIL#",        // optional ticket_id prefix filter
    "status": "FAILED",        // optional status filter (e.g. FAILED, SUCCESS)
    "dry_run": false,           // default false
    "max_delete": 10000         // default 10000
    }

Response:
    { "scanned": N, "matched": N, "deleted": N, "dry_run": true|false }

Environment variables:
    SERVICE_NOW_TICKETS_TABLE   e.g. uk-snowfall-dev-service-now-tickets
"""

import os

import boto3
from boto3.dynamodb.conditions import Attr

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]

dynamodb = boto3.resource("dynamodb")
tickets_table = dynamodb.Table(SERVICE_NOW_TICKETS_TABLE)


def _coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def lambda_handler(event, context):  # noqa: ARG001
    event = event or {}
    prefix = str(event.get("prefix", "")).strip()
    status = str(event.get("status", "")).strip().upper()
    dry_run = _coerce_bool(event.get("dry_run", False), default=False)
    max_delete = int(event.get("max_delete", 10000))

    print(f"[INFO] Cleanup starting. table={SERVICE_NOW_TICKETS_TABLE} "
          f"prefix={prefix!r} status={status!r} dry_run={dry_run} max_delete={max_delete}")

    # Default behavior: no filter -> delete all rows (FAILED + SUCCESS + others).
    scan_kwargs = {"ProjectionExpression": "ticket_id"}
    filter_expr = None
    if prefix:
        filter_expr = Attr("ticket_id").begins_with(prefix)
    if status:
        status_expr = Attr("status").eq(status)
        filter_expr = status_expr if filter_expr is None else (filter_expr & status_expr)
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    matched_keys = []
    scanned = 0
    while True:
        resp = tickets_table.scan(**scan_kwargs)
        scanned += resp.get("ScannedCount", 0)
        for item in resp.get("Items", []):
            tid = item.get("ticket_id")
            if tid:
                matched_keys.append(tid)
                if len(matched_keys) >= max_delete:
                    break
        if len(matched_keys) >= max_delete or "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    matched = len(matched_keys)
    print(f"[INFO] Scanned={scanned} Matched={matched}")

    if dry_run:
        print("[INFO] DRY RUN — no deletions performed. "
              f"Sample of first 5: {matched_keys[:5]}")
        return {
            "scanned": scanned,
            "matched": matched,
            "deleted": 0,
            "dry_run": True,
            "status": status,
            "prefix": prefix,
            "sample": matched_keys[:5],
        }

    deleted = 0
    for tid in matched_keys:
        tickets_table.delete_item(Key={"ticket_id": tid})
        deleted += 1
        if deleted % 25 == 0:
            print(f"[INFO] Deleted {deleted}/{matched}")

    print(f"[INFO] Cleanup complete. deleted={deleted}")
    return {
        "scanned": scanned,
        "matched": matched,
        "deleted": deleted,
        "dry_run": False,
        "status": status,
        "prefix": prefix,
    }
