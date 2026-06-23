"""
ServiceNow Tickets Cleanup Lambda (DEV utility)
Bulk-deletes rows from alert/ticket tables used by proactive testing.

DEFAULT BEHAVIOR:
    - Invoking without payload deletes all rows in the configured target tables.
    - Targets include SERVICE_NOW_TICKETS_TABLE and PROACTIVE_ALERTS_TABLE.
    - EXTRA_CLEANUP_TABLES (comma-separated) can add more tables.
    - You can still use prefix/status to narrow the rows.
    - MAX_DELETE caps how many rows can be deleted per invocation.

Invocation event (all fields optional):
    {
    "prefix": "ALERT#",        // optional id prefix filter (ticket_id/alert_id)
    "status": "FAILED",        // optional status filter (e.g. FAILED, SUCCESS)
    "dry_run": false,           // default false
    "max_delete": 10000         // default 10000
    }

Response:
    {
      "scanned": N,
      "matched": N,
      "deleted": N,
      "dry_run": true|false,
      "tables": [{"table": "...", "scanned": N, "matched": N, "deleted": N}]
    }

Environment variables:
    SERVICE_NOW_TICKETS_TABLE   e.g. uk-snowfall-dev-service-now-tickets
    PROACTIVE_ALERTS_TABLE      e.g. uk-snowfall-dev-proactive-alerts
    EXTRA_CLEANUP_TABLES        optional comma-separated additional tables
    CLEANUP_TABLE_KEY_MAP       optional JSON map of table -> key names.
                                Example:
                                {"my-table": ["pk", "sk"], "other-table": ["id"]}
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
PROACTIVE_ALERTS_TABLE = os.environ.get("PROACTIVE_ALERTS_TABLE", "").strip()
EXTRA_CLEANUP_TABLES = os.environ.get("EXTRA_CLEANUP_TABLES", "").strip()
CLEANUP_TABLE_KEY_MAP = os.environ.get("CLEANUP_TABLE_KEY_MAP", "").strip()

dynamodb = boto3.resource("dynamodb")


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


def _build_target_tables():
    tables = [SERVICE_NOW_TICKETS_TABLE]
    if PROACTIVE_ALERTS_TABLE:
        tables.append(PROACTIVE_ALERTS_TABLE)
    if EXTRA_CLEANUP_TABLES:
        for raw in EXTRA_CLEANUP_TABLES.split(","):
            name = raw.strip()
            if name:
                tables.append(name)

    # preserve order while de-duplicating
    seen = set()
    unique = []
    for name in tables:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _parse_key_map(raw_value):
    if not raw_value:
        return {}
    try:
        value = json.loads(raw_value)
        if isinstance(value, dict):
            parsed = {}
            for table_name, keys in value.items():
                if isinstance(keys, str):
                    key_list = [k.strip() for k in keys.split(",") if k.strip()]
                elif isinstance(keys, list):
                    key_list = [str(k).strip() for k in keys if str(k).strip()]
                else:
                    continue
                if key_list:
                    parsed[str(table_name).strip()] = key_list
            return parsed
    except json.JSONDecodeError:
        print("[WARN] CLEANUP_TABLE_KEY_MAP is not valid JSON; ignoring")
    return {}


def _resolve_key_names(table_name, event_key_map):
    # Defaults for known Snowfall tables.
    if table_name == SERVICE_NOW_TICKETS_TABLE:
        return ["ticket_id"]
    if PROACTIVE_ALERTS_TABLE and table_name == PROACTIVE_ALERTS_TABLE:
        return ["alert_id"]

    # Per-invocation override has priority.
    if table_name in event_key_map:
        return event_key_map[table_name]

    # Environment-level mapping for additional tables.
    env_key_map = _parse_key_map(CLEANUP_TABLE_KEY_MAP)
    if table_name in env_key_map:
        return env_key_map[table_name]

    # Safe fallback for unknown tables without key metadata permission.
    return ["ticket_id"]


def _build_projection_expression(key_names):
    names = {f"#k{i}": key for i, key in enumerate(key_names)}
    projection = ", ".join(names.keys())
    return projection, names


def _select_prefix_attr(key_names):
    for preferred in ("ticket_id", "alert_id"):
        if preferred in key_names:
            return preferred
    return key_names[0] if key_names else None


def _collect_keys_to_delete(table, key_names, prefix, status, remaining_delete_budget):
    projection, names = _build_projection_expression(key_names)
    scan_kwargs = {
        "ProjectionExpression": projection,
        "ExpressionAttributeNames": names,
    }

    filter_expr = None
    if prefix:
        prefix_attr = _select_prefix_attr(key_names)
        if prefix_attr:
            filter_expr = Attr(prefix_attr).begins_with(prefix)
    if status:
        status_expr = Attr("status").eq(status)
        filter_expr = status_expr if filter_expr is None else (filter_expr & status_expr)
    if filter_expr is not None:
        scan_kwargs["FilterExpression"] = filter_expr

    matched_keys = []
    scanned = 0
    while True:
        resp = table.scan(**scan_kwargs)
        scanned += resp.get("ScannedCount", 0)
        for item in resp.get("Items", []):
            key = {name: item[name] for name in key_names if name in item}
            if len(key) == len(key_names):
                matched_keys.append(key)
                if len(matched_keys) >= remaining_delete_budget:
                    break

        if len(matched_keys) >= remaining_delete_budget or "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    return scanned, matched_keys


def lambda_handler(event, context):  # noqa: ARG001
    event = event or {}
    prefix = str(event.get("prefix", "")).strip()
    status = str(event.get("status", "")).strip().upper()
    dry_run = _coerce_bool(event.get("dry_run", False), default=False)
    max_delete = int(event.get("max_delete", 10000))

    target_tables = _build_target_tables()
    print(
        f"[INFO] Cleanup starting. tables={target_tables} prefix={prefix!r} "
        f"status={status!r} dry_run={dry_run} max_delete={max_delete}"
    )

    table_summaries = []
    total_scanned = 0
    total_matched = 0
    total_deleted = 0
    remaining_budget = max_delete

    for table_name in target_tables:
        if remaining_budget <= 0:
            table_summaries.append(
                {"table": table_name, "scanned": 0, "matched": 0, "deleted": 0, "skipped": True}
            )
            continue

        table = dynamodb.Table(table_name)
        event_key_map = _parse_key_map(json.dumps(event.get("table_key_map", {})))
        key_names = _resolve_key_names(table_name, event_key_map)
        try:
            scanned, matched_keys = _collect_keys_to_delete(
                table=table,
                key_names=key_names,
                prefix=prefix,
                status=status,
                remaining_delete_budget=remaining_budget,
            )
        except ClientError as exc:
            message = str(exc)
            print(f"[ERROR] {table_name}: scan failed: {message}")
            table_summaries.append(
                {
                    "table": table_name,
                    "scanned": 0,
                    "matched": 0,
                    "deleted": 0,
                    "error": message,
                }
            )
            continue

        matched = len(matched_keys)
        total_scanned += scanned
        total_matched += matched

        if dry_run:
            table_summaries.append(
                {
                    "table": table_name,
                    "scanned": scanned,
                    "matched": matched,
                    "deleted": 0,
                    "sample": matched_keys[:5],
                }
            )
            remaining_budget -= matched
            continue

        deleted_here = 0
        delete_error = ""
        for key in matched_keys:
            try:
                table.delete_item(Key=key)
            except ClientError as exc:
                delete_error = str(exc)
                print(f"[ERROR] {table_name}: delete failed for key {key}: {delete_error}")
                break
            deleted_here += 1
            if deleted_here % 25 == 0:
                print(f"[INFO] {table_name}: deleted {deleted_here}/{matched}")

        total_deleted += deleted_here
        remaining_budget -= deleted_here
        table_summaries.append(
            {
                "table": table_name,
                "scanned": scanned,
                "matched": matched,
                "deleted": deleted_here,
                **({"error": delete_error} if delete_error else {}),
            }
        )
        print(f"[INFO] {table_name}: scanned={scanned} matched={matched} deleted={deleted_here}")

    print(
        f"[INFO] Cleanup complete. scanned={total_scanned} matched={total_matched} "
        f"deleted={total_deleted}"
    )
    return {
        "scanned": total_scanned,
        "matched": total_matched,
        "deleted": total_deleted,
        "dry_run": dry_run,
        "status": status,
        "prefix": prefix,
        "tables": table_summaries,
    }
