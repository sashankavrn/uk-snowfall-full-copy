# JIRA: NCR Voyix Incident Management Integration – Snowfall Proactive Alerts

---

## Overview

**Title**: NCR Voyix Incident Management Integration – Snowfall Proactive Alerts  
**Project**: UK Snowfall  
**Issue Type**: Story  
**Priority**: Medium  
**Labels**: `ncr-servicenow`, `integration`, `proactive-alerts`, `snowfall`, `rest-api`  
**Epic Description**:

> Integrate the McDonald's UK Snowfall proactive alerts Lambda with the NCR Voyix Incident Management
> REST API so that device incidents detected by Snowfall automatically raise, update, and resolve
> tickets in the NCR Voyix system (backed by ServiceNow).
>
> When a proactive alert fires (e.g. a restaurant device issue detected via Athena query), the system
> calls NCR's `CreateRequest` REST endpoint to open a ticket. The full `IncidentUpdate` (including
> `NCRTicketID`, `TicketStatus`, and all ticket fields) is returned **synchronously** in the same
> `CreateResponse`. No separate async callback is required for ticket creation. NCR may still send
> async `IncidentUpdate` callbacks to our API Gateway for subsequent lifecycle changes
> (e.g. Tech Dispatched → Closed) — secured with Basic Auth (confirmed 23 Apr 2026).
>
> **Architecture**:
> ```
> snowfall-proactive-alerts Lambda  (existing — scan rules, send email)
>   │  async invoke (InvocationType=Event — fire and forget, no wait)
>   ▼
> snowfall-ncr-servicenow-ticket Lambda  (NEW — NCR ticket lifecycle only)
>   │  loads Basic Auth credentials from Secrets Manager
>   │  HTTPS POST JSON (Authorization: Basic <base64> header)
>   ▼
> NCR Voyix ESB → ServiceNow
>   │  Sync CreateResponse → full IncidentUpdate returned (TicketID, TicketStatus, etc.)
>   │  stores ncr_servicenow_ticket_id / ncr_servicenow_create_status / ticket status in DynamoDB
>   │
>   │  Async IncidentUpdate callbacks (lifecycle updates: Dispatched, Closed etc.)
>   │  NCR authenticates with Basic Auth header (confirmed 23 Apr 2026)
>   ▼
> AWS API Gateway (POST /ncr-servicenow-callback, port 443)
>   ▼
> snowfall-ncr-servicenow-callback Lambda  (NEW — lifecycle status updates only)
>   ▼
> DynamoDB (proactive_alerts_table)
> ```
>
> **Design decision**: NCR ticket logic is isolated in `snowfall-ncr-servicenow-ticket` Lambda.
> The alerts Lambda fires it asynchronously (fire-and-forget) so email sending is never
> delayed or blocked by NCR API latency or failures. A Dead Letter Queue (DLQ) on the
> NCR ticket Lambda catches any invocation failures for manual review.
>
> **API Type**: REST, JSON payloads over HTTPS  
> **Reference**: NCR Voyix Standard Restaurant Incident Management Web Services Technical Doc V1.1 (Feb 2024)  
> **Mapping doc**: `docs/NCR Voyix Restaurant Standard Mapping Doc.xlsx`  
> **Sample messages**: `docs/Sample Messages for Restaurant Incident Management Interface.pdf`  
> **Engineering doc**: `docs/ncr-integration-auth-setup.md`

---

## STORY 1 — NCR Onboarding & Credential Provisioning

**Title**: NCR Voyix onboarding – obtain credentials, REST endpoints and confirm field mappings  
**Issue Type**: Story  
**Priority**: Highest  
**Description**:
> All engineering work is blocked on NCR provisioning credentials and confirming field mappings.
> This story tracks all items that must be obtained from the NCR Voyix integration onboarding team.
> Reference Q&A document: `docs/ncr-integration-auth-setup.md`.
>
> NCR Voyix inbound REST authentication — confirmed from live CERT connectivity test (22 Apr 2026):
> - **Auth**: HTTP Basic Auth (`Authorization: Basic <base64(user:pass)>` header) — confirmed working
> - **Note**: Original tech doc (v3.2) described WS-Security + mTLS; actual CERT interface uses Basic Auth. Confirm if PROD requires mTLS in addition.
> - WS-Security `USERID`/`Password` are sent inside the JSON `Header` block on every request (separate from HTTP Basic Auth)

**Acceptance Criteria**:
- [x] CERT REST endpoint URL confirmed — `https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest`
- [x] CERT endpoint connectivity confirmed via NCR sample Postman collection (HTTP 200, 22 Apr 2026) — uses NCR's shared sample credentials
- [ ] Our dedicated CERT Basic Auth credentials provisioned by NCR (separate account per business process)
- [ ] PROD REST endpoint URL received from NCR
- [ ] Our dedicated PROD Basic Auth credentials provisioned by NCR
- [ ] Confirm whether PROD requires mTLS client certificate in addition to Basic Auth
- [ ] `MCN`, `SourceSystem`, `SiteNumber` format, `RequestType`, `Category`/`SubCategory`, `CustomerName` values confirmed
- [x] NCR callback authentication method decided (Basic auth confirmed as option — 15 Apr 2026)

---

### Task 1.1
**Title**: Raise NCR Voyix integration onboarding request  
**Description**: Contact the NCR Voyix integration/onboarding team to formally request a new customer integration. Reference: NCR Voyix Standard Restaurant Incident Management Web Services Technical Doc V1.1 (Feb 2024).  
**Priority**: Highest

---

### Task 1.2
**Title**: Schedule NCR Voyix onboarding call  
**Description**: Book the onboarding call with the NCR Voyix integration team. Prepare and share the Q&A document (`docs/ncr-integration-auth-setup.md`) ahead of the call.  
**Priority**: Highest

---

### Task 1.3
**Title**: Obtain CERT environment REST endpoint URL and credentials from NCR  
**Status**: 🔄 **IN PROGRESS — endpoint confirmed, dedicated credentials pending**  
**Description**: NCR provided a **sample Postman collection** (`MCDUK`) for initial connectivity testing:
- CERT REST endpoint URL confirmed: `https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest`
- Connectivity test using NCR's **sample credentials** (`MA230518`) returned HTTP 200 — endpoint reachable, Basic Auth accepted
- ⚠️ `MA230518` is NCR's **shared sample test account** from the Postman collection — not our dedicated integration credentials
- ⚠️ Sample body uses `CountryCode: "US"` and `USERID: "USERID"` (placeholders) — our requests must use `CountryCode: "GB"` and our provisioned `USERID`
- Business validation error (`Customer Name` field missing) returned on test — expected for sample data; connectivity confirmed

**Still required from NCR**:
- Our dedicated CERT `USERID` and `Password` (NCA/SOUP domain account, unique per business process)  
**Priority**: High  
**Blocked by**: Task 1.2

---

### Task 1.4
**Title**: Obtain PROD environment REST endpoint URL and credentials from NCR  
**Description**: NCR to provide:
- PROD REST endpoint URL (HTTPS, port 443)
- PROD Basic Auth `USERID` (separate account from CERT — one unique ID per business process)
- PROD `Password` (rotate annually)
- Confirm whether PROD requires mTLS client certificate in addition to Basic Auth (CERT does not appear to require it based on sample Postman test)  
**Priority**: High  
**Blocked by**: Task 1.2

---

### Task 1.5
**Title**: Confirm customer field mappings with NCR (mapping session)  
**Description**: In the onboarding mapping session confirm:
- `MCN` value for McDonald's UK (master customer number)
- `SourceSystem` string NCR expects in the `Header` (e.g. `MCDONALDS_UK`) — Postman example shows `CUSTOMERAPP`
- `CustomerName` — **blocking field**: live CERT test (22 Apr 2026) returned `FaultCode: NCR ERROR` → `"Customer Name"` missing/invalid; confirm expected field name and value (likely company name e.g. `"McDonalds UK"`)
- Restaurant number format → `SiteNumber` mapping (e.g. `"1234"`) — Postman uses `Site.SiteNumber` (not `SiteShortName` from old SOAP doc)
- `RequestType` values to use for hardware vs software alerts (`HW` / `SW`) — Postman example shows `"Hardware"`
- `Category` and `SubCategory` valid values for restaurant device alerts
- `Priority` scale: 1 = Critical, 2 = Urgent, 3 = Normal, 4 = Low
- Confirm if `ATMCustomerMetrics` / `NCRMCN` / `CI.AssetID` fields are required for McDonald's UK tickets (present in old SOAP doc; absent from REST Postman example)

Reference: `CreateRequest-ToNCR Voyix` sheet in `NCR Voyix Restaurant Standard Mapping Doc.xlsx`.  
**Priority**: High  
**Blocked by**: Task 1.2

---

### Task 1.6
**Title**: Confirm NCR outbound callback authentication method  
**Status**: ✅ **DONE — confirmed in meeting 15 Apr 2026**  
**Description**: Confirmed — NCR supports two options for authenticating their outbound `IncidentUpdate` REST calls to our API Gateway:
1. **Basic Auth** — NCR sends `Authorization: Basic <base64(user:pass)>` header on each call
2. **Client Certificate** — NCR presents a certificate on the HTTPS connection (inbound mTLS on our side)

Decision on which to implement is pending (see Story 7). Basic Auth is recommended.  
**Priority**: High

---

### Task 1.7
**Title**: Obtain NCR callback credentials based on chosen auth method  
**Description**: Once Story 7 decision is made:
- **If Basic Auth**: Request the username + password NCR will send in the `Authorization` header. Store in AWS Secrets Manager as `ncr-servicenow/callback-auth` `{ "username": "TBC", "password": "TBC" }`.
- **If Client Cert**: Obtain NCR's certificate CA details for registration in our API Gateway truststore.  
**Priority**: High  
**Blocked by**: Task 7.1

---

## STORY 2 — SSL Client Certificate Procurement & Registration

**Title**: Procure and register SSL client certificates for mTLS — CERT + PROD environments  
**Issue Type**: Story  
**Priority**: High  
**Description**:
> NCR Voyix requires 2-factor authentication for all inbound REST calls.
> Factor 2 is SSL mutual TLS (mTLS): our Lambda must present a **commercial client certificate**
> on every HTTPS connection to the NCR REST endpoint. NCR validates the certificate at the TLS layer.
>
> Certificate requirements (per NCR Voyix V1.1 spec):
> - Must be issued by a **trusted global CA**: Symantec, GoDaddy, Thawte, Comodo, or GeoTrust
> - URL must be HTTPS
> - CN name must include and match the customer name (McDonald's UK)
> - Must not be expired or revoked (CRL reachable or OCSP used)
> - **Separate certificates required for CERT and PROD** — NCR does NOT recommend sharing certs across environments
> - Private key must never leave AWS Secrets Manager

**Acceptance Criteria**:
- CERT client certificate purchased from NCR-approved CA, CSR generated, signed, and registered with NCR
- PROD client certificate purchased from NCR-approved CA, CSR generated, signed, and registered with NCR
- Private keys stored in AWS Secrets Manager (`ncr-servicenow/client-key-cert`, `ncr-servicenow/client-key-prod`)
- NCR confirms both certificates are active in their system before testing begins

---

### Task 2.1
**Title**: Purchase commercial SSL certificate for CERT environment  
**Description**: Purchase from one of the NCR-approved CAs: Symantec, GoDaddy, Thawte, Comodo, or GeoTrust. Standard SSL/TLS certificate used for client authentication (mTLS).  
**Priority**: High

---

### Task 2.2
**Title**: Generate CSR and private key — CERT environment  
**Description**: Once CN name format is confirmed with NCR (Task 1.5), generate using openssl:
```bash
openssl req -new -newkey rsa:2048 -nodes \
  -keyout mcdonalds-uk-ncr-cert.key \
  -out    mcdonalds-uk-ncr-cert.csr \
  -subj "/CN=<confirm-with-NCR>/O=McDonalds UK Ltd/C=GB"
```
Store private key securely — it goes straight into Secrets Manager; never committed to git.  
**Priority**: High  
**Blocked by**: Task 1.5

---

### Task 2.3
**Title**: Submit CSR to CA and receive signed certificate — CERT environment  
**Description**: Submit the `.csr` file to the chosen commercial CA. Store the returned signed `.crt` PEM. Expected CA turnaround: 1–5 business days.  
**Priority**: High  
**Blocked by**: Task 2.2

---

### Task 2.4
**Title**: Register client certificate with NCR — CERT environment  
**Description**: Send the signed public `.crt` (never the private key) to the NCR Voyix integration team for registration. Confirm registration is active before running any CERT tests.  
**Priority**: High  
**Blocked by**: Task 2.3

---

### Task 2.5
**Title**: Purchase commercial SSL certificate for PROD environment  
**Description**: Same CA and process as CERT. NCR Voyix V1.1 spec explicitly requires separate certificates for CERT and PROD environments.  
**Priority**: Medium

---

### Task 2.6
**Title**: Generate CSR and private key — PROD environment  
**Description**: Same process as Task 2.2, separate key pair for PROD.  
**Priority**: Medium  
**Blocked by**: Task 1.5

---

### Task 2.7
**Title**: Submit CSR to CA and receive signed certificate — PROD environment  
**Description**: Same process as Task 2.3 for PROD environment.  
**Priority**: Medium  
**Blocked by**: Task 2.6

---

### Task 2.8
**Title**: Register client certificate with NCR — PROD environment  
**Description**: Same process as Task 2.4 for PROD environment.  
**Priority**: Medium  
**Blocked by**: Task 2.7

---

## STORY 3 — AWS Infrastructure

**Title**: AWS infrastructure for NCR Voyix integration (Secrets Manager, IAM, callback Lambda, API Gateway, DynamoDB, Terraform)  
**Issue Type**: Story  
**Priority**: High  
**Description**:
> All AWS infrastructure work can be built now, independently of NCR onboarding.
> This story covers Secrets Manager secrets, IAM policy updates, the new callback Lambda,
> its API Gateway endpoint, DynamoDB schema additions, and all Terraform.

**Acceptance Criteria**:
- Secrets Manager secrets created (placeholder values until NCR provides real credentials)
- IAM roles updated with least-privilege permissions
- `snowfall-ncr-servicenow-callback` Lambda deployed and reachable on HTTPS port 443
- DynamoDB `proactive_alerts_table` updated with NCR ticket tracking attributes
- All resources managed via Terraform in `terraform/core_delta_lake/`

---

### Task 3.1
**Title**: Create Secrets Manager secrets for NCR credentials  
**Description**: Create the following AWS Secrets Manager secrets (placeholder values now, real values populated when available from ncr-servicenow/CA):

| Secret name | Contents |
|---|---|
| `ncr-servicenow/credentials-cert` | `{ "userid": "TBC", "password": "TBC" }` — CERT WS-Security creds |
| `ncr-servicenow/credentials-prod` | `{ "userid": "TBC", "password": "TBC" }` — PROD WS-Security creds |
| `ncr-servicenow/client-cert-cert` | PEM certificate string — CERT mTLS client cert |
| `ncr-servicenow/client-key-cert` | PEM private key string — CERT mTLS private key |
| `ncr-servicenow/client-cert-prod` | PEM certificate string — PROD mTLS client cert |
| `ncr-servicenow/client-key-prod` | PEM private key string — PROD mTLS private key |
| `ncr-servicenow/callback-auth` | `{ "username": "TBC", "password": "TBC" }` — NCR callback Basic Auth creds |

**Priority**: High

---

### Task 3.2
**Title**: Update IAM role for proactive-alerts Lambda  
**Description**: Add `secretsmanager:GetSecretValue` permission scoped to `ncr-servicenow/*` secret ARNs on the `snowfall-proactive-alerts` Lambda execution role. Principle of least privilege — no wildcard resource.  
**Priority**: High

---

### Task 3.3
**Title**: Add NCR ticket tracking fields to proactive_alerts_table (DynamoDB)  
**Description**: DynamoDB is schemaless — no migration needed. Update `record_email_alert()` to write the following new attributes:

| Attribute | Set when | Example value |
|---|---|---|
| `ncr_servicenow_transaction_id` | On `CreateRequest` sent | `"3f2a1b..."` (our UUID) |
| `ncr_servicenow_create_status` | On `CreateRequest` response | `"SUCCESS"` / `"FAILED"` / `"SKIPPED"` |
| `ncr_servicenow_ticket_id` | On `CreateRequest` sync response | `"01956911"` (returned immediately by NCR REST API) |
| `ncr_servicenow_ticket_status` | On `IncidentUpdate` callback | `"In Progress"` / `"Open Tech Dispatched"` / `"Closed"` |
| `ncr_servicenow_tech_eta` | On `IncidentUpdate` callback | `"2026-04-20T10:00:00"` |
| `ncr_servicenow_complete_date` | On `IncidentUpdate` callback | `"2026-04-21T15:30:00"` |

**Priority**: High

---

### Task 3.4
**Title**: Build snowfall-ncr-servicenow-callback Lambda  
**Description**: New Lambda to receive `IncidentUpdate` REST JSON POST callbacks from NCR Voyix.

Responsibilities:
1. Validate incoming auth header (Basic Auth or cert — per Story 7 decision)
2. Parse `IncidentUpdateRequestMessage.IncidentUpdate` JSON body; extract:
   - `CustomerTicketID` — our original `alert_id` (used as DynamoDB lookup key)
   - `TicketID` — NCR's ticket reference
   - `TicketStatus` — e.g. `In Progress`, `Open Tech Dispatched`, `Closed Template Complete`
   - Logistics fields: `TechETA`, `TechArrival`, `ShipDate`, `PartETA`, `CompleteDate`, `CaseID`, `CaseStatus`
3. Handle **2-Way Create** scenario: `CustomerTicketID` = `null` means NCR has raised a ticket manually in their system; create a new DynamoDB record and return our ticket number
4. `update_item` in DynamoDB with all received fields
5. Return ACK JSON within 5 seconds:
   - Success: `{ "result": "success", "message": "<our_alert_id>" }`
   - Failure: `{ "errorCode": "<code>", "message": "<description>" }`

**Priority**: High

---

### Task 3.5
**Title**: Build API Gateway REST endpoint for NCR callback  
**Description**: Create a REST API Gateway with:
- Resource: `POST /ncr-servicenow-callback`
- Integration: Lambda proxy → `snowfall-ncr-servicenow-callback`
- Stage: `prod`, HTTPS port 443 (API Gateway default — no custom port needed)
- Secured via Lambda authorizer (Story 7)

Provide the final URL to NCR integration team for registration.  
**Priority**: High

---

### Task 3.6
**Title**: Write Terraform for callback Lambda, API Gateway, IAM, and invoke permissions  
**Description**: Add Terraform resources in `terraform/core_delta_lake/`:

**Callback Lambda + API Gateway** (NCR → us):
- `aws_lambda_function` — `snowfall-ncr-servicenow-callback`
- `aws_iam_role` + policy — DynamoDB `UpdateItem` + `GetItem`, Secrets Manager `GetSecretValue` on `ncr-servicenow/callback-auth`
- `aws_api_gateway_rest_api`, resource, method, integration, deployment, stage
- `aws_lambda_permission` — allow API Gateway to invoke callback Lambda
- `aws_api_gateway_authorizer` — Lambda authorizer for Basic Auth (or mTLS config if cert chosen)

**proactive-alerts → ncr-ticket invoke permission** (us → our own Lambda):
- Add `lambda:InvokeFunction` on `snowfall-ncr-servicenow-ticket` ARN to the `snowfall-proactive-alerts` IAM role
- Add `NCR_SERVICENOW_ENABLED` and `NCR_SERVICENOW_TICKET_LAMBDA_ARN` env vars to `snowfall-proactive-alerts` Lambda  
**Priority**: High

---

## STORY 4 — Engineering: snowfall-ncr-servicenow-ticket Lambda (NCR REST API Integration)

**Title**: Build `snowfall-ncr-servicenow-ticket` Lambda — NCR Voyix CreateRequest / UpdateRequest / ResolveRequest  
**Issue Type**: Story  
**Priority**: High  
**Description**:
> Build a **new dedicated Lambda** (`snowfall-ncr-servicenow-ticket`) to handle all NCR Voyix ticket operations.
> The existing `snowfall-proactive-alerts` Lambda invokes this Lambda **asynchronously**
> (`InvocationType=Event`) — fire-and-forget — so email delivery is never delayed or
> blocked by NCR API latency or failures.
>
> **API**: REST POST, `Content-Type: application/json`, HTTPS with mTLS client cert
> **Auth**: WS-Security credentials (`USERID` + `Password`) in JSON `Header` block on every request
> **Reference**: NCR Voyix Technical Doc V1.1, `Sample Messages for Restaurant Incident Management Interface.pdf`
>
> Key behaviour:
> - Triggered by async invoke from `snowfall-proactive-alerts` with alert payload as event
> - NCR `CreateRequest` returns the `TicketID` **synchronously** in the response
> - `UpdateRequest` adds remarks to an existing ticket (NCR `TicketID` required)
> - `ResolveRequest` closes the ticket (ticket must be in Customer Queue for resolve to work)
> - Lambda DLQ (SQS) catches invocation failures for manual review

**Acceptance Criteria**:
- `snowfall-proactive-alerts` async-invokes `snowfall-ncr-servicenow-ticket` after email step; does not wait for response
- `create_ncr_servicenow_ticket()` sends valid JSON `CreateRequest` and stores `ncr_servicenow_ticket_id` from sync response
- `update_ncr_servicenow_ticket()` sends valid JSON `UpdateRequest` with existing `TicketID` and remark text
- `resolve_ncr_servicenow_ticket()` sends valid JSON `ResolveRequest` with `TicketID`, `ResolutionCategory`, `ResolutionNotes`
- mTLS certs loaded from Secrets Manager at cold start, reused on warm invocations
- `ncr_servicenow_transaction_id`, `ncr_servicenow_create_status`, `ncr_servicenow_ticket_id` stored in DynamoDB after `CreateRequest`
- NCR failures logged and written to DynamoDB; do not propagate to alerts Lambda
- All string fields sanitised and length-limited before sending
- DLQ configured on `snowfall-ncr-servicenow-ticket` Lambda for failed async invocations

---

### Task 4.1
**Title**: Implement mTLS certificate loading from Secrets Manager  
**Description**: Implement `_load_mtls_certs()` function:
- Reads `ncr-servicenow/client-cert-{env}` and `ncr-servicenow/client-key-{env}` from Secrets Manager on cold start
- Writes PEM strings to `/tmp/ncr-cert.pem` and `/tmp/ncr-key.pem` (ephemeral, never persisted)
- Reuses files on warm invocations (check file exists before re-fetching)
- `NCR_SERVICENOW_ENV` read from Lambda environment variable (`cert` or `prod`)  
**Priority**: High

---

### Task 4.2
**Title**: Implement create_ncr_servicenow_ticket() — CreateRequest  
**Description**: Build the `CreateRequest` REST call. JSON payload structure (per V1.1 spec and sample messages):
```json
{
  "Header": {
    "TransactionID": "<uuid-per-alert>",
    "USERID": "<from-secrets-manager>",
    "SourceSystem": "<confirmed-with-NCR>",
    "TimeStamp": "<ISO-8601-UTC>"
  },
  "CreateServiceRequest": {
    "CountryCode": "GB",
    "CustomerTicketID": "<alert_id>",
    "RequestType": "<HW|SW>",
    "Priority": <1-4>,
    "Summary": "<≤100 chars>",
    "Description": "<≤4000 chars>",
    "MCN": "<mcdonalds-uk-mcn>",
    "Category": "<category>",
    "SubCategory": "<subcategory>",
    "Site": { "SiteNumber": "<restaurant-number>" },
    "Remark": { "Text": "<optional-remark>" }
  }
}
```
- POST to `NCR_SERVICENOW_ENDPOINT` with `headers={"Authorization": "Basic <base64>"}`, `verify=True`, `timeout=30`
- Parse **full sync `IncidentUpdate` response** — confirmed 23 Apr 2026: the complete ticket object is returned synchronously, not via async callback:
  - `Header.Status` — `SUCCESS` / `FAILURE`
  - `Header.Fault.FaultCode` + `Header.Fault.FaultDescription`
  - `NCRIncidentUpdate.NCRTicketID` — NCR's ticket reference
  - `NCRIncidentUpdate.TicketStatus` — initial status (e.g. `Open`)
  - `NCRIncidentUpdate.TechETA`, `NCRIncidentUpdate.CaseID`, other logistics fields if present
- Write all received fields to DynamoDB in the same invocation (no need to wait for async callback for initial ticket data)
- Return `(transaction_id, "SUCCESS"/"FAILED", ncr_servicenow_ticket_id, fault_description)`  
**Priority**: High  
**Blocked by**: Task 4.1

---

### Task 4.3
**Title**: Implement update_ncr_servicenow_ticket() — UpdateRequest  
**Description**: Build the `UpdateRequest` REST call to add a remark to an existing NCR ticket:
```json
{
  "Header": { "TransactionID": "...", "USERID": "...", "SourceSystem": "..." },
  "UpdateServiceRequest": {
    "TicketID": "<ncr-ticket-id>",
    "CountryCode": "GB",
    "Remark": { "Text": "<remark-text-≤4000-chars>" }
  }
}
```
Use case: alert condition changes after ticket is open (e.g. device partially recovered — add a status note).
Parse response `Header.Status` and `Header.Fault.FaultCode`.  
**Priority**: Medium  
**Blocked by**: Task 4.2

---

### Task 4.4
**Title**: Implement resolve_ncr_servicenow_ticket() — ResolveRequest  
**Description**: Build the `ResolveRequest` REST call to close an NCR ticket when an alert auto-resolves:
```json
{
  "Header": { "TransactionID": "...", "USERID": "...", "SourceSystem": "..." },
  "UpdateServiceRequest": {
    "TicketID": "<ncr-ticket-id>",
    "CountryCode": "GB",
    "ResolutionCategory": "<category>",
    "ResolutionNotes": "<notes-≤4000-chars>"
  }
}
```
Note: ticket must be in Customer Queue for `ResolveRequest` to work — confirm valid queue names with NCR.
Parse response `Header.Status` and `Header.Fault.FaultCode`.  
**Priority**: Medium  
**Blocked by**: Task 4.2

---

### Task 4.5
**Title**: Add field sanitisation and length enforcement  
**Description**: All user-generated string fields must be sanitised before sending to NCR:
- `Summary`: truncate to 100 chars; append `[..]` if truncated
- `Description`, `Remark.Text`, `ResolutionNotes`: truncate to 4000 chars; append `[TRUNCATED]` if truncated
- Strip control characters (newlines within JSON strings must be `\n`, not literal newlines)
- Applied in a shared `_sanitise_field(value, max_len)` helper  
**Priority**: High

---

### Task 4.6
**Title**: Wire async invoke of snowfall-ncr-servicenow-ticket into process_rule() flow with per-rule cooldown check  
**Description**: After the email step in `process_rule()`, check the NCR-specific cooldown **before** invoking the NCR ticket Lambda. The cooldown period is stored **per rule** in the `RULES_TABLE` DynamoDB as `ncr_servicenow_cooldown_hours` — the same pattern already used by `email_cooldown_hours`. Logic:

```python
# 1. Feature flag — is NCR enabled globally?
if os.environ.get('NCR_SERVICENOW_ENABLED', 'false').lower() != 'true':
    return  # NCR disabled globally — skip

# 2. Rule-level NCR flag — does this rule raise NCR tickets?
if not rule.get('ncr_servicenow_enabled', False):
    return  # this rule is not configured to raise NCR tickets — skip

# 3. Per-rule NCR cooldown check
#    Rule has: ncr_servicenow_cooldown_hours (int) — same pattern as email_cooldown_hours
ncr_servicenow_cooldown_hours = int(rule.get('ncr_servicenow_cooldown_hours', 24))

existing = proactive_alerts_table.query(
    IndexName='rule_id-index',
    FilterExpression=Attr('rule_id').eq(rule['rule_id']) & Attr('ncr_servicenow_create_status').eq('SUCCESS')
)
if existing['Items']:
    last_ticket = max(existing['Items'], key=lambda x: x.get('last_alert_time', ''))
    elapsed = hours_since(last_ticket.get('last_alert_time'))
    if elapsed < ncr_servicenow_cooldown_hours:
        logger.info(f"NCR cooldown active for rule {rule['rule_id']} — skipping invoke")
        return

# 4. Cooldown passed — async invoke NCR ticket Lambda (fire and forget)
boto3.client('lambda').invoke(
    FunctionName=os.environ['NCR_SERVICENOW_TICKET_LAMBDA_ARN'],
    InvocationType='Event',
    Payload=json.dumps({
        'alert_id': alert_id,
        'rule_id': rule['rule_id'],
        'site_number': site_number,
        'summary': summary,
        'description': description,
        'priority': rule.get('ncr_servicenow_priority', 3),
        'request_type': rule.get('ncr_servicenow_request_type', 'HW'),
    })
)
```

**Rules table additions** (`RULES_TABLE` DynamoDB) — new optional fields per rule:

| Field | Type | Description |
|---|---|---|
| `ncr_servicenow_enabled` | Boolean | `true` = this rule raises an NCR ticket on violation |
| `ncr_servicenow_cooldown_hours` | Number | Hours before a second NCR ticket can be raised for same rule (e.g. `24`) |
| `ncr_servicenow_priority` | Number | NCR ticket priority: 1=Critical, 2=Urgent, 3=Normal, 4=Low |
| `ncr_servicenow_request_type` | String | `HW` or `SW` — maps to NCR `RequestType` |

- Rules without `ncr_servicenow_enabled: true` are silently skipped — no impact on existing rules
- If invoke API call itself fails: log error only — do **not** raise or block email  
**Priority**: High  
**Blocked by**: Task 4.2, Task 3.3

---

### Task 4.7
**Title**: Add Terraform for snowfall-ncr-servicenow-ticket Lambda + IAM + DLQ + env vars  
**Description**: Add Terraform resources in `terraform/core_delta_lake/`:

**New resources for `snowfall-ncr-servicenow-ticket`**:
- `aws_lambda_function` — `snowfall-ncr-servicenow-ticket`, with DLQ (`aws_sqs_queue` → `aws_lambda_function.dead_letter_config`)
- `aws_iam_role` + `aws_iam_role_policy` — Secrets Manager `GetSecretValue` on `ncr-servicenow/*`, DynamoDB `PutItem` + `UpdateItem` on `proactive_alerts_table`
- `aws_sqs_queue` — `snowfall-ncr-servicenow-ticket-dlq` for failed async invocations

**Environment variables for `snowfall-ncr-servicenow-ticket`**:

| Variable | Description |
|---|---|
| `NCR_SERVICENOW_ENV` | `"cert"` (non-prod) / `"prod"` (prod) |
| `NCR_SERVICENOW_ENDPOINT` | REST endpoint URL provided by NCR |
| `NCR_SERVICENOW_MCN` | McDonald's UK MCN confirmed by NCR |
| `NCR_SERVICENOW_SOURCE_SYSTEM` | `SourceSystem` value confirmed by NCR |

**Updates to `snowfall-proactive-alerts`**:
- Add `lambda:InvokeFunction` permission on `snowfall-ncr-servicenow-ticket` ARN to its IAM role
- Add env vars:

| Variable | Description |
|---|---|
| `NCR_SERVICENOW_ENABLED` | `"true"` / `"false"` — feature flag |
| `NCR_SERVICENOW_TICKET_LAMBDA_ARN` | ARN of `snowfall-ncr-servicenow-ticket` Lambda |
| `NCR_SERVICENOW_COOLDOWN_HOURS` | Hours to suppress duplicate tickets per rule+site (default `24`) |

**Priority**: Medium

---

## STORY 5 — CERT Environment Testing

**Title**: End-to-end integration testing on NCR Voyix CERT environment  
**Issue Type**: Story  
**Priority**: High  
**Description**: Full end-to-end testing against NCR Voyix CERT (test/QA) environment before any PROD activity.  
**Blocked by**: Stories 1, 2, 3, 4, 7 complete

**Acceptance Criteria**:
- `CreateRequest` successfully creates a ticket in NCR CERT; full `IncidentUpdate` (TicketID, TicketStatus, etc.) returned in sync response and all fields stored in DynamoDB
- `UpdateRequest` adds a remark to the created ticket; `SUCCESS` response received
- `ResolveRequest` closes the ticket; `SUCCESS` response received
- NCR CERT async `IncidentUpdate` lifecycle callback (Dispatched/Closed) received by our API Gateway with Basic Auth header, parsed correctly, DynamoDB updated
- 2-Way Create callback handled: NCR-initiated ticket creates new DynamoDB record
- Duplicate ticket prevention (cooldown) validated
- One ticket per restaurant validated (not one bulk ticket)
- CERT sign-off obtained from NCR Voyix integration team

---

### Task 5.1
**Title**: Provide NCR with our callback endpoint URL  
**Description**: Share the API Gateway URL (`POST /ncr-servicenow-callback`, HTTPS port 443) with the NCR Voyix integration team for registration as the outbound `IncidentUpdate` endpoint. NCR must register it before callback messages are sent.  
**Priority**: High

---

### Task 5.2
**Title**: CERT test — CreateRequest creates ticket successfully  
**Description**: Trigger the proactive-alerts Lambda manually. Verify the REST `CreateRequest` JSON call reaches the NCR CERT endpoint, response `Header.Status` = `SUCCESS`, `NCRIncidentUpdate.NCRTicketID` received and stored in `ncr_servicenow_ticket_id` DynamoDB field.  
**Priority**: High

---

### Task 5.3
**Title**: CERT test — IncidentUpdate data returned in sync CreateRequest response  
**Description**: Verify that the synchronous `CreateRequest` response contains the full `IncidentUpdate` block (confirmed 23 Apr 2026): `NCRTicketID`, `TicketStatus`, and logistics fields are populated in the response and written to DynamoDB immediately within the same Lambda invocation — no separate callback needed for initial ticket data.  
Also test NCR async lifecycle callbacks (Dispatched/Closed): verify that NCR calls our `/ncr-servicenow-callback` API Gateway endpoint with `Authorization: Basic` header, the callback Lambda validates auth, parses `TicketID` and `TicketStatus`, and updates DynamoDB. Callback Lambda responds with `{ "result": "success", "message": "..." }` within 5 seconds.  
**Priority**: High

---

### Task 5.4
**Title**: CERT test — cooldown prevents duplicate tickets  
**Description**: Trigger the same rule twice within the cooldown window. Verify only one NCR `CreateRequest` is sent; second trigger is blocked by cooldown logic and `ncr_servicenow_create_status = "SKIPPED"`.  
**Priority**: High

---

### Task 5.5
**Title**: CERT test — one ticket per restaurant  
**Description**: Trigger a rule with multiple violating restaurants. Verify a separate NCR `CreateRequest` is sent per restaurant, each with its own `CustomerTicketID` and `SiteNumber`.  
**Priority**: Medium

---

### Task 5.6
**Title**: CERT test — 2-Way Create (NCR-initiated ticket)  
**Description**: NCR Voyix manually raises a ticket on their side and sends an `IncidentUpdate` callback with `CustomerTicketID` set to `null` or `""`. Verify the callback Lambda creates a new DynamoDB record with `ncr_servicenow_ticket_id` populated and `customer_ticket_id` blank (to be back-filled if a matching rule fires later).  
**JSON shape expected:**
```json
{ "IncidentUpdateRequestMessage": { "Header": { "USERID": "...", "SourceSystem": "SOUP", "TransactionID": "...", "TimeStamp": "..." },
  "IncidentUpdate": { "CustomerTicketID": null, "TicketID": "02956861", "TicketStatus": "Open" } } }
```
**Priority**: Medium

---

### Task 5.7
**Title**: Obtain CERT environment sign-off from NCR Voyix  
**Description**: NCR Voyix integration team to formally confirm CERT testing is complete and approved to proceed to PROD cutover.  
**Priority**: High

---

## STORY 7 — Callback Authentication Implementation

**Title**: Decide and implement callback authentication for NCR → Our API Gateway  
**Issue Type**: Story  
**Priority**: High  
**Description**:
> NCR confirmed on 15 Apr 2026 that their outbound `IncidentUpdate` calls support two auth options.
> **Basic Auth confirmed as the chosen method (23 Apr 2026)** — NCR will send
> `Authorization: Basic <base64(user:pass)>` on every outbound callback to our API Gateway.
> Client Certificate path is not required.
>
> Note: the initial `IncidentUpdate` (with `NCRTicketID` and `TicketStatus`) is returned
> **synchronously** in the `CreateRequest` response — confirmed 23 Apr 2026. Async callbacks
> from NCR are used only for subsequent lifecycle status changes (Dispatched, Closed etc.).

**Acceptance Criteria**:
- [x] Decision documented and agreed with NCR — **Basic Auth chosen (23 Apr 2026)**
- [ ] Lambda authorizer validates `Authorization: Basic <base64>` header; credentials stored in Secrets Manager `ncr-servicenow/callback-auth`
- ~~If Client Cert: API Gateway custom domain with mutual TLS enabled; NCR's cert CA registered~~ *(not required — Basic Auth confirmed)*
- [ ] Unauthorised requests return HTTP 401
- [ ] Terraform updated for Basic Auth authorizer
- [ ] End-to-end tested in CERT environment

---

### Task 7.1
**Title**: Decide on callback auth method (Basic auth vs client cert) and confirm with NCR  
**Status**: ✅ **DONE — Basic Auth confirmed by NCR (23 Apr 2026)**  
**Description**: NCR confirmed Basic Auth is the chosen callback authentication method. NCR will send `Authorization: Basic <base64(user:pass)>` header on all outbound `IncidentUpdate` calls to our API Gateway. Client Certificate path is not required.  
Document decision in `docs/ncr-integration-auth-setup.md`. Obtain NCR's Basic Auth username and password for the callback.  
**Priority**: Highest  
**Blocked by**: Task 1.7

---

### Task 7.2
**Title**: Implement Lambda authorizer for NCR callback endpoint (Basic Auth path)  
**Description**: If Basic Auth is chosen: create an API Gateway Lambda authorizer that:
1. Reads `Authorization: Basic <base64>` header
2. Decodes and compares against credentials stored in `ncr-servicenow/callback-auth` (Secrets Manager)
3. Returns IAM `Allow` policy on match, `Deny` on mismatch
4. Authorizer result cached for 0 seconds (NCR sends different transactions, caching not appropriate)  
**Priority**: High  
**Blocked by**: Task 7.1

---

### Task 7.3
**Title**: Implement inbound mTLS on API Gateway (Client Cert path)  
**Status**: 🚫 **NOT REQUIRED — Basic Auth confirmed (23 Apr 2026)**  
**Description**: ~~If Client Certificate is chosen: configure API Gateway custom domain with `mutualTlsAuthentication` truststore containing NCR's CA certificate.~~ Client Cert path not selected — Basic Auth confirmed. This task is closed.  
**Priority**: N/A

---

### Task 7.4
**Title**: Store callback auth secret in Secrets Manager + Terraform  
**Description**: Create `ncr-servicenow/callback-auth` Secrets Manager secret. Add to Terraform. Grant callback Lambda `secretsmanager:GetSecretValue` on this secret.  
**Priority**: High  
**Blocked by**: Task 7.1

---

### Task 7.5
**Title**: Test callback auth in CERT environment  
**Description**: Verify NCR CERT callbacks are accepted (HTTP 200 + ACK JSON), and that a call without valid auth returns HTTP 401. Log verified in CloudWatch.  
**Priority**: High  
**Blocked by**: Task 7.2 or 7.3

---

## STORY 6 — PROD Go-Live

**Title**: PROD environment deployment and go-live  
**Issue Type**: Story  
**Priority**: Medium  
**Description**: Repeat credential and certificate steps for PROD, deploy, and go live.  
**Blocked by**: Story 5 sign-off

---

### Task 6.1
**Title**: Populate PROD credentials and certificates in Secrets Manager  
**Description**: Replace placeholder values in `ncr-servicenow/credentials` (PROD), `ncr-servicenow/client-cert-prod`, `ncr-servicenow/client-key-prod` with real PROD values from NCR and the CA.  
**Priority**: Medium

---

### Task 6.2
**Title**: PROD smoke test: end-to-end ticket creation  
**Description**: Trigger one real proactive alert and verify the `CreateRequest` REST POST reaches the NCR PROD endpoint. Confirm `ncr_servicenow_ticket_id` is stored in the PROD DynamoDB table from the synchronous `CreateResponse` (`NCRIncidentUpdate.NCRTicketID`). Then verify an `IncidentUpdate` status callback is received and DynamoDB record updated.  
**Priority**: Medium

---

### Task 6.3
**Title**: PROD go-live sign-off and monitoring  
**Description**: Confirm with stakeholders that PROD integration is live. Set up CloudWatch alarm on `ncr_servicenow_create_status = FAILED` to alert on NCR call failures.  
**Priority**: Medium

---

## Summary

| Story | Tasks | Can start now? | Notes |
|---|---|---|---|
| 1 – NCR Onboarding | 7 tasks | ✅ In progress | Q16 callback auth ✅ answered 15 Apr 2026 |
| 2 – SSL Certificates | 8 tasks | ✅ Partially | Buy cert now; CN format TBC from NCR |
| 3 – AWS Infrastructure | 6 tasks | ✅ Yes | No NCR dependency; build now |
| 4 – Lambda Engineering | 7 tasks | ✅ Yes | REST JSON; Create/Update/Resolve; feature flag `NCR_SERVICENOW_ENABLED` |
| 5 – CERT Testing | 7 tasks | ❌ Blocked | Blocked on Stories 1+2+7; includes 2-Way Create test |
| 6 – PROD Go-Live | 3 tasks | ❌ Blocked | Blocked on Story 5 sign-off |
| 7 – Callback Auth | 5 tasks | ✅ Decision needed now | Basic Auth recommended; options confirmed 15 Apr 2026 |
| **Total** | **43 tasks** | | |
