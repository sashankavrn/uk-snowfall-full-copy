# Code Review — `servicenow-proactive-ticket-close` Lambda

> Review of `lambda_function.py` (NCR Voyix close/update ServiceNow ticket Lambda).
> Purpose: document current behaviour per function, known issues, and a backlog of
> features/improvements to add later.

---

## 1. Overview

This Lambda is invoked **asynchronously** by `snowfall-proactive-alerts` when a proactive
rule that previously had an OPEN ServiceNow case stops returning violations (issue
self-healed). It resolves the NCR ticket ID, POSTs an `UpdateServiceRequest` to the NCR
CSDI endpoint, and writes the close result back to two DynamoDB tables.

**Invocation event shape**
```json
{ "rule": { ...incident rule row... }, "case": { ...SERVICENOW_CASE row... } }
```

**Tables touched**
- `SERVICE_NOW_TICKETS_TABLE` — ticket rows keyed by `ticket_id` = `NCR#<id>`
- `PROACTIVE_ALERTS_TABLE` — case rows keyed by `alert_id`

---

## 2. Function-by-function review

### `lambda_handler(event, context)`
**Does:** Orchestrates the whole close flow — validates `case`, resolves NCR ticket ID,
builds + sends the update payload, parses the response, updates both tables, returns an
HTTP-style result.

| Aspect | Notes |
|---|---|
| Guard clause | Returns `400` if `case` missing — good. |
| No-ticket path | If no NCR ticket ID, marks case `CLOSED` with `ncr_status="SKIPPED"` and returns `200`. Reasonable, but see Issue #2. |
| Response parsing | Reads `response["IncidentUpdate"]["TicketID"]` — **likely wrong field names** (see Issue #3). |
| Success gating | Case only marked `CLOSED` on `ncr_status == "SUCCESS"`; otherwise state left unchanged → **case can get stuck** (Issue #1). |
| Return | `200` on success, `502` on non-success. `returned_ticket_id` only logged. |

### `_resolve_ncr_ticket_id(case)`
**Does:** Returns NCR ticket ID from `case["ncr_ticket_id"]`, else scans
`SERVICE_NOW_TICKETS_TABLE` by `source_alert_id` + `status == "SUCCESS"`.

| Aspect | Notes |
|---|---|
| Fallback lookup | Paginated scan — correct. |
| Performance | Full-table `scan` with `FilterExpression`; fine at low volume, costly at scale (Issue #5). |
| Ambiguity | Uses `items[0]` if multiple SUCCESS rows exist — no ordering guarantee. |

### `_build_update_payload(ncr_ticket_id, case, rule)`
**Does:** Constructs the NCR `UpdateServiceRequest` JSON (Header + body with resolution
notes and remark).

| Aspect | Notes |
|---|---|
| TransactionID | Epoch-ms string — acts as idempotency key. Good. |
| `CountryCode` | Defaults to `"UK"` — **NCR expects ISO `"GB"`** (Issue #4). |
| Resolution notes | Branches on whether a proactive script ran — nice, human-readable. |
| Single-line desc | `splitlines()[0]` avoids multi-line summary issues. |

### `_get_ncr_credentials()`
**Does:** Fetches URL + Basic-auth creds from Secrets Manager; caches in module global.

| Aspect | Notes |
|---|---|
| URL resolution | env override → update-url → resolve-url → derived from create-url. Robust. |
| Caching | Per-container cache — only refreshes on cold start (acceptable; note for rotation). |
| Validation | Raises `RuntimeError` if URL/user/pass missing — good fail-fast. |

### `_post_to_ncr(payload)`
**Does:** POSTs JSON with Basic auth via `urllib`, returns parsed JSON or a synthetic
error envelope.

| Aspect | Notes |
|---|---|
| **SSL** | Defaults to **disabled cert verification** (`CERT_NONE`) — security risk (Issue #1/Sec). |
| Redundant branch | `if VERIFY_SSL` and `else` create the same context before disabling checks. |
| Error handling | `URLError` → CONNECTION_ERROR envelope; `HTTPError` falls through to JSON parse; non-JSON → INVALID_JSON envelope. Decent coverage. |
| No retry | Single attempt; transient failures not retried (Issue #6). |

### `_update_ticket_resolved(ncr_ticket_id, ncr_status, fault_description)`
**Does:** Sets `resolved_at`, `ncr_close_status`, `close_notes` on the ticket row.

| Aspect | Notes |
|---|---|
| Always runs | Updates ticket row regardless of success/failure — useful audit trail. |
| Swallows errors | Catches all exceptions, logs `[WARN]` — won't fail the invocation. |

### `_mark_case_closed(case_id, ncr_ticket_id, ncr_status)`
**Does:** Sets case `status = CLOSED`, `last_updated_at`, `ncr_close_status`, optionally
`ncr_ticket_id`.

| Aspect | Notes |
|---|---|
| Reserved word | Uses `#s` alias for `status` — correct. |
| Conditional attr | Only sets `ncr_ticket_id` when present — clean. |
| Swallows errors | Catches all, logs `[WARN]`. If this fails after a successful NCR close, case stays `CLOSING` (Issue #7). |

---

## 3. Known issues / risks

| # | Severity | Issue | Suggested fix |
|---|---|---|---|
| 1 | High (Security) | SSL verification disabled by default (`NCR_VERIFY_SSL` defaults `"false"`). MITM risk. | Default to `"true"`; only disable in dev. Remove redundant `if/else` branch. |
| 2 | High (Ops) | On NCR failure / connection error / invalid JSON, case left in `CLOSING`. `get_open_servicenow_case` only matches `OPEN`, so it's never retried — NCR ticket silently stays open. | Revert case to `OPEN` on failure, or add retry/DLQ. |
| 3 | Medium | Response parsed as `IncidentUpdate.TicketID`; confirmed NCR shape uses `NCRIncidentUpdate.NCRTicketID`. `returned_ticket_id` likely always `None`. | Align field names with confirmed NCR response. |
| 4 | Medium | `CountryCode` defaults to `"UK"`; NCR uses ISO `"GB"`. May be rejected. | Default to `"GB"`. |
| 5 | Low | `_resolve_ncr_ticket_id` uses full-table scan. | Add GSI on `alert_id`/`source_alert_id` and query. |
| 6 | Low | No retry on transient NCR errors. | Add bounded retry w/ backoff, or rely on async retry + DLQ. |
| 7 | Low | If `_mark_case_closed` fails after successful NCR close, case stuck in `CLOSING`. | Add alarm/DLQ; consider conditional update + alerting. |

---

## 4. Feature backlog (add later)

- [ ] **Idempotency guard** — skip if case already `CLOSED` (handle duplicate async invokes).
- [ ] **DLQ + alarm** — configure Lambda DLQ and CloudWatch alarm on failures/stuck `CLOSING`.
- [ ] **Structured logging** — replace `print` with `logging` + JSON formatter for queryable logs.
- [ ] **Metrics** — emit CloudWatch metrics: close success/failure counts, NCR latency.
- [ ] **Retry/backoff** — bounded retry for transient NCR/HTTP errors.
- [ ] **GSI-backed lookup** — replace ticket-table scan with a query.
- [ ] **Schema validation** — validate `event["case"]`/`["rule"]` shape (e.g. with a small validator).
- [ ] **Response shape alignment** — confirm and map `NCRIncidentUpdate`/`NCRTicketID`.
- [ ] **Reopen safety** — if NCR reports already-closed/unknown ticket, branch accordingly.
- [ ] **Unit tests** — mock Secrets Manager, DynamoDB, and NCR HTTP; cover success + each failure path.
- [ ] **Type hints + docstrings** — complete coverage for maintainability.
- [ ] **Config defaults review** — `SOURCE_SYSTEM`, `USER_ID`, `CountryCode` confirmed against NCR.

---

## 5. Quick wins (low-risk, high-value)

1. Default `NCR_VERIFY_SSL` to `true` and collapse the duplicate SSL branch.
2. Change `CountryCode` default `"UK"` → `"GB"`.
3. Revert case to `OPEN` (not leave `CLOSING`) on non-success.
4. Fix NCR response field names (`NCRIncidentUpdate.NCRTicketID`).
