# NCR ServiceNow Ticket Creation Lambda — Engineering Notes

**Service**: `uk-snowfall-dev-servicenow-proactive-ticket`
**Code**: `uk-snowfall-data-pipeline/terraform/core_delta_lake/lambda/scripts/python/servicenow-proactive-ticket-creation/lambda_function.py`
**Terraform**: `uk-snowfall-data-pipeline/terraform/core_delta_lake/lambda/main.tf` (block `uk_snowfall_servicenow_proactive_ticket`)
**Region**: `eu-central-1`
**Account**: `295446674139`
**Status**: ✅ Live in DEV — first successful production-pattern ticket created `NCR#CS2021862` (restaurant 282)

---

## 1. Architecture

```
proactive-alerts Lambda
    │  (async invoke — Event)
    ▼
servicenow-proactive-ticket Lambda  ◄── Secrets Manager: uk-snowfall-ncr-servicenow
    │
    │  HTTPS POST (Basic Auth)
    ▼
NCR CSDI REST endpoint
    │
    │  HTTP 200 sync response (Status SUCCESS|FAILURE, NCRTicketID)
    ▼
DynamoDB: uk-snowfall-dev-service-now-tickets
```

- Invoked **asynchronously** by `snowfall-proactive-alerts` lambda via `SERVICENOW_TICKET_LAMBDA` env var.
- Single payload per restaurant violation; one row per NCR call written to ticket DDB table (whether SUCCESS or FAILURE).

---

## 2. NCR API Contract (confirmed live 2026-04-22 → 2026-04-23)

### Endpoint (CERT)
```
POST https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest
Authorization: Basic <base64(username:password)>
Content-Type: application/json
```

### Auth — Secrets Manager
Secret: `uk-snowfall-ncr-servicenow` (region `eu-central-1`)
Keys:
- `uk-snowfall-ncr-servicenow-url`
- `uk-snowfall-ncr-servicenow-username`
- `uk-snowfall-ncr-servicenow-password`

Lambda caches creds across warm invocations via module-level `_NCR_CREDS` dict.

### Request body (working)
```json
{
  "Header": {
    "TransactionID": "<epoch-ms — see idempotency note>",
    "USERID": "<from secret>",
    "SourceSystem": "CUSTOMERAPP",
    "TimeStamp": "<ISO 8601 UTC>"
  },
  "CreateServiceRequest": {
    "CountryCode": "GB",
    "CustomerTicketID": "<rule_id or alert_id>",
    "RequestType": "Hardware",
    "Priority": 2,
    "Summary": "<≤160 chars currently — doc allows 255>",
    "Description": "<≤4000 chars>",
    "Category": "Hardware",
    "Subcategory": "<e.g. Cash Drawer>",
    "Caller": {
      "FirstName": "Snowfall",
      "LastName": "Alerts"
    },
    "Site": { "SiteNumber": "0282" },
    "Remark": { "Text": "<optional>" }
  }
}
```

### Response
- HTTP 200 always (even on business failure — must check `Header.Status`).
- `Header.Status` ∈ `SUCCESS` | `FAILURE`
- `Header.SourceSystem` = `"SOUP"` (NCR's internal echo, not what we send)
- On SUCCESS: `NCRIncidentUpdate.NCRTicketID` populated immediately (sync) — full IncidentUpdate also returned
- On FAILURE: `Header.Fault.FaultCode = "NCR ERROR"`, `Header.Fault.FaultDescription` names invalid fields (e.g. `|Customer Name|`, `Site or PID`)

---

## 3. Confirmed Live Behaviours

| Finding | Evidence | Status |
|---|---|---|
| `Site.SiteNumber` must be **zero-padded to 4 digits** | Postman sample `"0114"`; restaurant `59` failed, `0282` succeeded | ✅ Fixed via `str(restaurant_id).zfill(4)` |
| Basic Auth works (no mTLS on CERT) | First 200 OK with creds-only headers | ✅ |
| `CreateServiceRequest` returns full `IncidentUpdate` synchronously | Field present in success response | ✅ Documented |
| Async outbound callback uses Basic Auth (NCR → us) | NCR confirmed 2026-04-23 | Pending callback endpoint impl |
| NCR `SourceSystem` echo = `"SOUP"`, not what we sent | Observed in every response | ✅ Documented |

---

## 4. Known Gaps vs Requirements Doc (`Localfiles/snowfall-docs/ncr_ticket_requrments`)

| Gap | Current | Should be | Priority |
|---|---|---|---|
| **Idempotency** | `TransactionID = epoch-ms` (changes every retry) | `TransactionID = alert_id` (or deterministic hash) so NCR de-dupes retries | 🔴 High |
| **CountryCode** | Hardcoded `"GB"` | UK / IE based on `restaurant_id < 7000 ? GB : IE` | 🟡 Medium |
| **Subcategory casing** | `Subcategory` (camel) | Doc shows `SubCategory` (Pascal) — confirm with NCR which works | 🟡 Medium |
| **Summary length** | Truncated to 160 chars | Doc allows 255 | 🟢 Low |
| **ServiceOffering** | Sent in payload | Doc says "[Not exposed]" — drop it | 🟢 Low |
| **`Caller.LastName`** required | Hardcoded `"Alerts"` | Confirm McD UK expected caller; first failure was `"Customer Name"` missing | 🟡 Medium |

---

## 5. Close-Sync Pipeline Status (verified via AWS CLI 2026-05-10, clarified 2026-05-11)

The close-sync flow will need to query the `service_case` Athena view in PROD — **the DEV ingest has been intentionally stopped**, only PROD receives current `service_case` updates from NCR.

### DEV findings (account 295446674139) — expected stale

| Check | Result |
|---|---|
| Athena view `uk_snowfall_semantic.ncr_service_now_service_case_latest` row count | 40,853 rows |
| Most recent `sys_updated_timestamp_utc` | 2026-01-20 17:07:22 UTC (stale by design — DEV ingest stopped) |
| Test ticket `CS2021862` (created via DEV API today) | Not in view (expected — DEV ingest stopped) |
| S3 raw prefix `s3://eu-central1-dev-uk-snowfall-raw-295446674139/ncr_service_now/service_case/` | Only an empty 0-byte placeholder dated 2025-04-16 |
| AppFlow for service_case in DEV | Does not exist (only Incident-Intraday, ChangeRequest etc.) |
| EventBridge rule `uk-snowfall-ncr-service-now-service-case-trigger-rule` | Present but inactive — nothing lands in S3 |
| Underlying base table | `uk_snowfall_processed.ncr_service_now_service_case` (`_latest` is a `ROW_NUMBER` view over it) |

### Implication
- **DEV close-sync via Athena cannot be tested against fresh data.** Tickets created in DEV against NCR CERT will never appear in the DEV Athena view.
- **PROD is the only environment where the close-sync Athena flow will work end-to-end.** Build and verify the close-sync lambda against the PROD `ncr_service_now_service_case_latest` view.
- For DEV testing of the close-sync lambda logic, options:
  - **Option A** (preferred): Read-only cross-account Athena access from DEV lambda → PROD Athena view (requires PROD IAM role + Lake Formation grant).
  - **Option B**: Seed DEV DDB ticket table with known PROD case numbers and run the lambda against PROD Athena directly during validation.
  - **Option C**: Restore the DEV `service_case` AppFlow purely for parity — only worth it if cost is negligible and the team wants full DEV/PROD symmetry.

### NCR ingest schedule (PROD pattern, from DEV AppFlow `UK-SNowFall-ServiceNow-Incident-Intraday` as reference)
- Cron: `cron(30 6-20 ? * MON-FRI *)` GMT
- Hourly at :30 past, 06:30–20:30, weekdays only (no weekend runs)
- **Confirm the same cadence on the PROD `service_case` ingest before locking the close-sync schedule.**
- Recommended close-sync schedule (subject to PROD confirmation): `cron(45 6-20 ? * MON-FRI *)` — 15 min after upstream lands.

---

## 6. Recommended Next Actions

### Immediate (this lambda)
1. **Idempotency fix** — change `TransactionID` to deterministic `alert_id` value.
2. **CountryCode logic** — UK/IE branching by restaurant_id.
3. **Confirm `SubCategory` vs `Subcategory`** with NCR (one HTTP 400 test will tell us).
4. **Cleanup** — delete legacy `uk_snowfall_ncr_servicenow_ticket_create` connectivity-test lambda + `ncr-servicenow-ticket-create-connectivity-test/` folder.

### Close-sync
- Build close-sync lambda targeting the **PROD** `ncr_service_now_service_case_latest` view (DEV ingest is intentionally stopped).
- Verify PROD `service_case` ingest cadence (assumed `cron(30 6-20 ? * MON-FRI *)` GMT — same as Incident-Intraday pattern).
- Decide DEV testing approach: cross-account Athena read from DEV → PROD, or validate directly in PROD with seeded DDB rows.
- Schedule (recommended): `cron(45 6-20 ? * MON-FRI *)` — 15 min after upstream lands.

### Pending NCR confirmation
- PROD endpoint URL + credentials
- Whether PROD requires mTLS (CERT does not)
- `NCRMCN` value for McDonald's UK (only needed if NCR rejects without it)
- Final list of valid `Subcategory` values for UK hardware tickets
- Caller field requirements (the `"Customer Name"` failure suggests our caller block may need extra fields)

---

## 7. DynamoDB Schema (`uk-snowfall-dev-service-now-tickets`)

| Attribute | Notes |
|---|---|
| `ticket_id` (PK) | `NCR#<NCRTicketID>` on success, `FAIL#<transaction_id>` on failure |
| `transaction_id` | Echoed from `Header.TransactionID` |
| `rule_id` | Source rule that triggered the alert |
| `alert_id` | From proactive-alerts payload |
| `restaurant_id` | Numeric restaurant number (pre-zero-pad) |
| `site_number` | Zero-padded 4-digit string sent to NCR |
| `status` | `SUCCESS` \| `FAILURE` |
| `ncr_ticket_id` | NCR's case number on success |
| `fault_code` / `fault_description` | NCR fault details on failure |
| `request_payload` | Full JSON sent to NCR (audit) |
| `response_payload` | Full JSON returned by NCR (audit) |
| `created_at` | ISO 8601 UTC timestamp |
| `closed_at` *(future)* | To be populated by close-sync flow once Option A/B chosen |
| `ncr_state` *(future)* | NCR ticket state on closure |
| `close_notes` *(future)* | NCR `close_notes` field |
| `resolution_code` *(future)* | NCR `resolution_code` field |

---

## 8. Test Evidence

- ✅ Successful ticket: `NCR#CS2021862` — restaurant 282, site `"0282"`, Priority 2, Hardware/Cash Drawer
- ❌ First-attempt failure (pre-fix): restaurant `59` → fault `"Required proper Site or PID information is not correct"`
- ❌ Earlier failure: missing `"Customer Name"` field — to revisit if it recurs

---

*Last updated: 2026-05-10*
