"""
ServiceNow Tickets Cleanup Lambda (DEV utility)
-----------------------------------------------
Bulk-deletes rows from the ServiceNow tickets table and/or the proactive-alerts
table (which holds EMAIL_ALERT and SERVICENOW_CASE records).

DEFAULT BEHAVIOR:
    - Invoking without payload deletes all rows in the tickets table only.
    - Use `target` to also (or instead) clear the proactive-alerts table.
    - You can still use prefix/status (tickets) or record_type (alerts) to narrow.
    - max_delete caps how many rows can be deleted per table per invocation.

Invocation event (all fields optional):
    {
    "target": "tickets",        // "tickets" (default) | "alerts" | "all"
    "prefix": "EMAIL#",        // tickets only: ticket_id prefix filter
    "status": "FAILED",        // tickets only: status filter (FAILED, SUCCESS)
    "record_type": "SERVICENOW_CASE", // alerts only: record_type filter
    "dry_run": false,           // default false
    "max_delete": 10000         // default 10000 (per table)
    }

Response:
    { "target": "...", "results": { "<table>": {scanned, matched, deleted} },
      "dry_run": true|false }

Environment variables:
    SERVICE_NOW_TICKETS_TABLE   e.g. uk-snowfall-dev-service-now-tickets
    PROACTIVE_ALERTS_TABLE      e.g. uk-snowfall-dev-proactive-alerts
"""

import os

import boto3
from boto3.dynamodb.conditions import Attr

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
PROACTIVE_ALERTS_TABLE = os.environ.get("PROACTIVE_ALERTS_TABLE", "")

dynamodb = boto3.resource("dynamodb")
tickets_table = dynamodb.Table(SERVICE_NOW_TICKETS_TABLE)
alerts_table = dynamodb.Table(PROACTIVE_ALERTS_TABLE) if PROACTIVE_ALERTS_TABLE else None


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


def _cleanup_table(table, key_attr, filter_expr, dry_run, max_delete):
    """Scan `table` for rows matching `filter_expr` and delete them by `key_attr`."""
    scan_kwargs = {"ProjectionExpression": key_attr}
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    matched_keys = []
    scanned = 0
    while True:
        resp = table.scan(**scan_kwargs)
        scanned += resp.get("ScannedCount", 0)
        for item in resp.get("Items", []):
            key_val = item.get(key_attr)
            if key_val:
                matched_keys.append(key_val)
                if len(matched_keys) >= max_delete:
                    break
        if len(matched_keys) >= max_delete or "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    matched = len(matched_keys)
    print(f"[INFO] {table.name}: Scanned={scanned} Matched={matched}")

    if dry_run:
        print(f"[INFO] {table.name}: DRY RUN - no deletions. "
              f"Sample of first 5: {matched_keys[:5]}")
        return {
            "scanned": scanned,
            "matched": matched,
            "deleted": 0,
            "sample": matched_keys[:5],
        }

    deleted = 0
    for key_val in matched_keys:
        table.delete_item(Key={key_attr: key_val})
        deleted += 1
        if deleted % 25 == 0:
            print(f"[INFO] {table.name}: Deleted {deleted}/{matched}")

    print(f"[INFO] {table.name}: Cleanup complete. deleted={deleted}")
    return {"scanned": scanned, "matched": matched, "deleted": deleted}


def lambda_handler(event, context):  # noqa: ARG001
    event = event or {}
    target = str(event.get("target", "tickets")).strip().lower()
    prefix = str(event.get("prefix", "")).strip()
    status = str(event.get("status", "")).strip().upper()
    record_type = str(event.get("record_type", "")).strip()
    dry_run = _coerce_bool(event.get("dry_run", False), default=False)
    max_delete = int(event.get("max_delete", 10000))

    print(f"[INFO] Cleanup starting. target={target!r} "
          f"prefix={prefix!r} status={status!r} record_type={record_type!r} "
          f"dry_run={dry_run} max_delete={max_delete}")

    results = {}

    if target in ("tickets", "all", "both"):
        ticket_filter = None
        if prefix:
            ticket_filter = Attr("ticket_id").begins_with(prefix)
        if status:
            status_expr = Attr("status").eq(status)
            ticket_filter = status_expr if ticket_filter is None else (ticket_filter & status_expr)
        results[SERVICE_NOW_TICKETS_TABLE] = _cleanup_table(
            tickets_table, "ticket_id", ticket_filter, dry_run, max_delete
        )

    if target in ("alerts", "all", "both"):
        if alerts_table is None:
            raise RuntimeError(
                "PROACTIVE_ALERTS_TABLE env var not set; cannot clean alerts table."
            )
        alert_filter = Attr("record_type").eq(record_type) if record_type else None
        results[PROACTIVE_ALERTS_TABLE] = _cleanup_table(
            alerts_table, "alert_id", alert_filter, dry_run, max_delete
        )

    if not results:
        raise ValueError(
            f"Invalid target {target!r}; expected 'tickets', 'alerts', or 'all'."
        )

    return {"target": target, "dry_run": dry_run, "results": results}
