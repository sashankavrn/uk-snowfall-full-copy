"""
ServiceNow Tickets Cleanup Lambda (DEV utility)
-----------------------------------------------
Bulk-deletes rows from `uk-snowfall-<env>-service-now-tickets` that match
an optional `ticket_id` prefix filter (e.g. "EMAIL#", "FAILED#", "NCR#").

SAFETY:
  - Defaults to DRY_RUN = true. You must explicitly pass {"dry_run": false}
    in the event to actually delete.
  - MAX_DELETE caps how many rows can be deleted per invocation.
  - Only operates on the table named in SERVICE_NOW_TICKETS_TABLE env var.

Invocation event (all fields optional):
    {
      "prefix":   "EMAIL#",      // ticket_id prefix to match. "" = match all.
      "dry_run":  true,          // default true. Set false to actually delete.
      "max_delete": 1000          // default 1000. Hard cap per invocation.
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


def lambda_handler(event, context):  # noqa: ARG001
    event = event or {}
    prefix = str(event.get("prefix", ""))
    dry_run = bool(event.get("dry_run", True))
    max_delete = int(event.get("max_delete", 1000))

    print(f"[INFO] Cleanup starting. table={SERVICE_NOW_TICKETS_TABLE} "
          f"prefix={prefix!r} dry_run={dry_run} max_delete={max_delete}")

    scan_kwargs = {"ProjectionExpression": "ticket_id"}
    if prefix:
        scan_kwargs["FilterExpression"] = Attr("ticket_id").begins_with(prefix)

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
    }
