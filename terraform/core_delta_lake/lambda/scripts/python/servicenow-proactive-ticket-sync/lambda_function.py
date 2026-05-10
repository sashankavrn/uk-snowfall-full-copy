"""
NCR ServiceNow Ticket Close-Sync Lambda
---------------------------------------
Scheduled lambda that reconciles open tickets in DynamoDB against the
NCR ServiceNow Athena view and marks them closed when NCR has closed them.

Flow:
  1. Scan `uk-snowfall-<env>-service-now-tickets` for open tickets:
       status = 'SUCCESS' AND ncr_ticket_id <> '' AND attribute_not_exists(closed_at)
  2. Batch the NCR case numbers (default 100 per Athena query).
  3. Query Athena view `uk_snowfall_semantic.ncr_service_now_service_case_latest`
     for any rows with state IN ('Closed','Resolved') for those case numbers.
  4. For each closed/resolved case → update_item on DDB to set
        closed_at, ncr_state, close_notes, resolution_code, resolved_at.
  5. Log summary counts.

NOTE: In DEV the upstream `service_case` ingest is intentionally stopped, so
this lambda will only update DDB rows whose ncr_ticket_id matches a historical
closed case in the DEV view. PROD has live data.

Environment variables:
    SERVICE_NOW_TICKETS_TABLE   e.g. uk-snowfall-dev-service-now-tickets
    ATHENA_DATABASE             default "uk_snowfall_semantic"
    ATHENA_VIEW                 default "ncr_service_now_service_case_latest"
    ATHENA_WORKGROUP            default "uk-snowfall-pipeline"
    ATHENA_OUTPUT_S3            REQUIRED s3:// path for query results
    ATHENA_REGION               default "eu-central-1"
    BATCH_SIZE                  default 100
    MAX_TICKETS_PER_RUN         default 500 (safety cap)
    QUERY_POLL_INTERVAL_SEC     default 2
    QUERY_TIMEOUT_SEC           default 60
"""

import os
import time
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SERVICE_NOW_TICKETS_TABLE = os.environ["SERVICE_NOW_TICKETS_TABLE"]
ATHENA_DATABASE = os.environ.get("ATHENA_DATABASE", "uk_snowfall_semantic")
ATHENA_VIEW = os.environ.get("ATHENA_VIEW", "ncr_service_now_service_case_latest")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "uk-snowfall-pipeline")
ATHENA_OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]
ATHENA_REGION = os.environ.get("ATHENA_REGION", "eu-central-1")

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
MAX_TICKETS_PER_RUN = int(os.environ.get("MAX_TICKETS_PER_RUN", "500"))
QUERY_POLL_INTERVAL_SEC = float(os.environ.get("QUERY_POLL_INTERVAL_SEC", "2"))
QUERY_TIMEOUT_SEC = int(os.environ.get("QUERY_TIMEOUT_SEC", "60"))

CLOSED_STATES = ("Closed", "Resolved")

dynamodb = boto3.resource("dynamodb")
tickets_table = dynamodb.Table(SERVICE_NOW_TICKETS_TABLE)
athena = boto3.client("athena", region_name=ATHENA_REGION)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):  # noqa: ARG001
    print(f"[INFO] Close-sync starting. table={SERVICE_NOW_TICKETS_TABLE} "
          f"view={ATHENA_DATABASE}.{ATHENA_VIEW}")

    open_tickets = _scan_open_tickets()
    print(f"[INFO] Found {len(open_tickets)} open ticket(s) to check")
    if not open_tickets:
        return {"checked": 0, "closed": 0, "batches": 0}

    # Map ncr_ticket_id -> ticket_id (DDB hash key) so we can update fast
    case_to_ticket = {t["ncr_ticket_id"]: t["ticket_id"] for t in open_tickets}
    case_numbers = list(case_to_ticket.keys())

    closed_count = 0
    batches = 0
    for batch in _chunks(case_numbers, BATCH_SIZE):
        batches += 1
        print(f"[INFO] Athena batch {batches}: {len(batch)} case numbers")
        closed_rows = _query_closed_cases(batch)
        print(f"[INFO] Athena returned {len(closed_rows)} closed/resolved rows in batch {batches}")
        for row in closed_rows:
            ticket_id = case_to_ticket.get(row["case_number"])
            if not ticket_id:
                continue
            _mark_ticket_closed(ticket_id, row)
            closed_count += 1

    print(f"[INFO] Close-sync complete. checked={len(open_tickets)} "
          f"closed={closed_count} batches={batches}")
    return {"checked": len(open_tickets), "closed": closed_count, "batches": batches}


# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------

def _scan_open_tickets() -> list:
    """Scan ticket table for SUCCESS tickets with no closed_at yet."""
    items: list = []
    scan_kwargs = {
        "FilterExpression": (
            Attr("status").eq("SUCCESS")
            & Attr("ncr_ticket_id").exists()
            & Attr("ncr_ticket_id").ne("")
            & Attr("closed_at").not_exists()
        ),
        "ProjectionExpression": "ticket_id, ncr_ticket_id",
    }
    while True:
        resp = tickets_table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            ncr = item.get("ncr_ticket_id")
            if ncr:
                items.append(item)
                if len(items) >= MAX_TICKETS_PER_RUN:
                    print(f"[WARN] Reached MAX_TICKETS_PER_RUN={MAX_TICKETS_PER_RUN}; "
                          "remaining open tickets will be processed next run")
                    return items
        if "LastEvaluatedKey" not in resp:
            break
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return items


def _mark_ticket_closed(ticket_id: str, row: dict) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    update_expr_parts = [
        "closed_at = :closed_at",
        "ncr_state = :ncr_state",
        "close_notes = :close_notes",
        "resolution_code = :resolution_code",
        "resolved_at = :resolved_at",
        "ncr_closed_timestamp = :ncr_closed_ts",
        "close_synced_at = :synced_at",
    ]
    values = {
        ":closed_at": row.get("closed_timestamp_utc") or now_iso,
        ":ncr_state": row.get("state", ""),
        ":close_notes": row.get("close_notes", "") or "",
        ":resolution_code": row.get("resolution_code", "") or "",
        ":resolved_at": row.get("resolved_timestamp_utc", "") or "",
        ":ncr_closed_ts": row.get("closed_timestamp_utc", "") or "",
        ":synced_at": now_iso,
    }
    tickets_table.update_item(
        Key={"ticket_id": ticket_id},
        UpdateExpression="SET " + ", ".join(update_expr_parts),
        ExpressionAttributeValues=values,
    )
    print(f"[INFO] Closed ticket {ticket_id} (case={row['case_number']}, state={row.get('state')})")


# ---------------------------------------------------------------------------
# Athena
# ---------------------------------------------------------------------------

def _query_closed_cases(case_numbers: list) -> list:
    """Run Athena query for the given case numbers; return list of dict rows."""
    # Quote each case number (varchar) and build IN clause. case_numbers are
    # NCR case strings (e.g. CS2021862) sourced from our own DDB so safe to inline.
    quoted = ", ".join(f"'{_sanitize(c)}'" for c in case_numbers)
    states_in = ", ".join(f"'{s}'" for s in CLOSED_STATES)
    sql = (
        f"SELECT case_number, state, resolved_timestamp_utc, "
        f"closed_timestamp_utc, close_notes, resolution_code "
        f"FROM {ATHENA_DATABASE}.{ATHENA_VIEW} "
        f"WHERE state IN ({states_in}) "
        f"AND case_number IN ({quoted})"
    )

    qid = athena.start_query_execution(
        QueryString=sql,
        WorkGroup=ATHENA_WORKGROUP,
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_S3},
    )["QueryExecutionId"]

    state = _wait_for_query(qid)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query {qid} ended with state={state}")

    return _fetch_results(qid)


def _wait_for_query(qid: str) -> str:
    deadline = time.time() + QUERY_TIMEOUT_SEC
    while True:
        status = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        state = status["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            if state != "SUCCEEDED":
                print(f"[ERROR] Athena query {qid} {state}: "
                      f"{status.get('StateChangeReason', '')}")
            return state
        if time.time() > deadline:
            raise TimeoutError(f"Athena query {qid} did not finish in {QUERY_TIMEOUT_SEC}s")
        time.sleep(QUERY_POLL_INTERVAL_SEC)


def _fetch_results(qid: str) -> list:
    rows: list = []
    paginator = athena.get_paginator("get_query_results")
    header = None
    for page in paginator.paginate(QueryExecutionId=qid):
        result_rows = page["ResultSet"]["Rows"]
        if header is None and result_rows:
            header = [c.get("VarCharValue") for c in result_rows[0]["Data"]]
            result_rows = result_rows[1:]
        for r in result_rows:
            data = [c.get("VarCharValue") for c in r["Data"]]
            rows.append(dict(zip(header, data)))
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _sanitize(value) -> str:
    """Strip single quotes to prevent broken SQL (defensive only)."""
    return str(value).replace("'", "")
