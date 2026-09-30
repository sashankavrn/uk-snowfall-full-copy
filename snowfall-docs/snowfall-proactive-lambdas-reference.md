# Snowfall Proactive Alerts — Lambda Reference

**Project:** McDonald's UK Snowfall Data Pipeline
**Region:** eu-central-1
**Last Updated:** April 2026

---

## Architecture Overview

```
EventBridge (scheduled)
        │
        ▼
snowfall-proactive-alerts          ← Main orchestrator
        │
        ├──► Athena (runs SQL queries per rule)
        │
        ├──► proactive-healing-connect/disconnect/monitor  (WebSocket management)
        │
        ├──► SMTP via Mailjet  (email alerts)
        │
        ├──► WebSocket API Gateway  (trigger scripts on devices)
        │          │
        │          ▼
        │    Service Agent (Windows service on restaurant devices)
        │          │
        │          ▼
        │    snowfall-proactive-healing-default  (receives results back)
        │
        └──► DynamoDB (proactive_alerts_table)

JWT Authorizer validates WebSocket connections before connect
```

---

## Lambda Functions

### 1. `snowfall-proactive-alerts`
**File:** `scripts/python/snowfall-proactive-alerts/lambda_function.py`
**Trigger:** EventBridge scheduled rule
**Purpose:** Main orchestrator — evaluates all active rules, sends emails, triggers proactive scripts

#### Environment Variables
| Variable | Description |
|---|---|
| `RULES_TABLE` | DynamoDB table containing alert rules |
| `PROACTIVE_ALERTS_TABLE` | DynamoDB table for alert history / cooldown tracking |
| `TABLE_NAME` | DynamoDB WebSocket connections table |
| `RESULTS_TABLE_NAME` | DynamoDB table for proactive script results |
| `ATHENA_OUTPUT_S3` | S3 bucket path for Athena query results |
| `STAGE_NAME` | `dev` / `nprod` / `prod` — controls WebSocket API endpoint URL |

#### Secrets Manager
- Secret: `uk-snowfall`
- Keys: `uk-snowfall-proactive-smpt-api-key`, `uk-snowfall-proactive-smpt-secret-key`

#### Execution Flow
```
1. Scan RULES_TABLE for all active rules (active = true)
2. For each rule:
   a. Run Athena query (rule["query"]) against database: uk_snowfall_processed
   b. If no results → skip
   c. If rule has proactive_script = true AND results contain restaurants:
      → Send script trigger via WebSocket to each connected device
      → Poll RESULTS_TABLE_NAME for up to 30 seconds
   d. Cooldown check against PROACTIVE_ALERTS_TABLE
      → Skip if same restaurants alerted within cooldown_hours
      → Allow if new restaurants detected (not in previous alert)
   e. If email_alert = true → send HTML email via Mailjet SMTP
   f. Record alert to PROACTIVE_ALERTS_TABLE (status: SENT or RECORDED)
```

#### Athena Query Format
Queries must return either:
- **1 column:** `message` — used for global (non-restaurant) rules
- **2 columns:** `restaurant_number`, `message` — used for per-restaurant rules

#### Cooldown Logic
- Cooldown tracked per `rule_id`
- Checks last `SENT` alert for the rule
- If new restaurant appears → bypass cooldown and send immediately
- If same restaurants and within cooldown window → suppress

#### Email
- Sender: `snowfall-proactive-alerts@ext.mcdonalds.com`
- SMTP: Mailjet (`in.mailjet.com:587`, STARTTLS)
- Subject format: `{incident_description} - [{count} Alerts]`
- HTML email includes: violation table + script results table (if applicable)

#### DynamoDB Record Written (`PROACTIVE_ALERTS_TABLE`)
| Field | Value |
|---|---|
| `alert_id` | `ALERT#<uuid>` |
| `record_type` | `EMAIL_ALERT` |
| `rule_id` | From rule |
| `restaurant_number` | First violating restaurant |
| `message` | First violation message |
| `status` | `SENT` or `RECORDED` |
| `created_at` | ISO timestamp (Europe/London) |
| `violating_restaurants` | List of all restaurant numbers |
| `last_alert_time` | ISO timestamp (Europe/London) |
| `email_recipients` | Comma-separated email list |

#### WebSocket Endpoints (by stage)
| Stage | Endpoint |
|---|---|
| `dev` | `https://vugx1b0qef.execute-api.eu-central-1.amazonaws.com/dev/` |
| `nprod` | `https://egnv9vgjjh.execute-api.eu-central-1.amazonaws.com/nprod/` |
| `prod` | `https://j3v4n25iwa.execute-api.eu-central-1.amazonaws.com/prod/` |

---

### 2. `snowfall-proactive-dynamodb-rules`
**File:** `scripts/python/snowfall-proactive-dynamodb-rules/lambda_function.py`
**Trigger:** Manual / one-time initialisation
**Purpose:** Seeds the DynamoDB rules table with placeholder rule records

#### Environment Variables
| Variable | Description |
|---|---|
| `RULES_TABLE` | DynamoDB rules table name |
| `NUM_RULES` | Number of placeholder rules to create (default: 10) |

#### Behaviour
- Scans existing `rule_id` values
- Creates missing rules (skips existing ones — idempotent)
- Each placeholder rule has `active: true`, `email_alert: true`, `servicenow_alert: true`, `proactive_script: true`
- All `query`, `email_dl`, `incident_description`, `proactive_script_name` fields are set to placeholder strings — **must be updated manually in DynamoDB after creation**

#### Rule Schema (DynamoDB)
| Field | Type | Description |
|---|---|---|
| `rule_id` | String (PK) | Unique rule identifier |
| `active` | Boolean | Whether rule is evaluated on each run |
| `query` | String | Athena SQL query |
| `incident_description` | String | Used in email subject and body |
| `email_alert` | Boolean | Whether to send email |
| `servicenow_alert` | Boolean | Whether to raise ServiceNow/NCR ticket (future) |
| `proactive_script` | Boolean | Whether to trigger a device script |
| `proactive_script_name` | String | Script name to send to service agent |
| `email_dl` | String | Comma or semicolon-separated email recipients |
| `email_cooldown_hours` | Number | Hours between repeat alerts for the same rule/restaurant |
| `created_at` | String | ISO timestamp |

---

### 3. `snowfall-proactive-healing-connect`
**File:** `scripts/python/snowfall-proactive-healing-connect/lambda_function.py`
**Trigger:** WebSocket API Gateway `$connect` route
**Purpose:** Stores new device WebSocket connection in DynamoDB

#### Environment Variables
| Variable | Description |
|---|---|
| `TABLE_NAME` | DynamoDB WebSocket connections table |

#### Behaviour
- Reads `restaurant_number`, `device_id`, `machine` from the JWT authorizer context (not query params)
- Requires JWT authorization to pass first (see authorizer below)
- Writes record with `status: connected` and `last_seen` timestamp

#### DynamoDB Record Written
| Field | Value |
|---|---|
| `restaurant_number` | From JWT authorizer context (PK) |
| `device_id` | From JWT authorizer context (SK) |
| `connectionId` | WebSocket connection ID |
| `machineName` | Machine name from JWT |
| `status` | `connected` |
| `last_seen` | UTC ISO timestamp |

---

### 4. `snowfall-proactive-healing-disconnect`
**File:** `scripts/python/snowfall-proactive-healing-disconnect/lambda_function.py`
**Trigger:** WebSocket API Gateway `$disconnect` route
**Purpose:** Marks device as disconnected in DynamoDB when WebSocket closes

#### Environment Variables
| Variable | Description |
|---|---|
| `TABLE_NAME` | DynamoDB WebSocket connections table |

#### Behaviour
- Scans connections table by `connectionId`
- Updates `status` to `disconnected` and sets `last_seen`
- Does not delete the record (keeps history)

---

### 5. `snowfall-proactive-healing-default`
**File:** `scripts/python/snowfall-proactive-healing-default/lambda_function.py`
**Trigger:** WebSocket API Gateway `$default` route (all non-connect/disconnect messages)
**Purpose:** Handles all inbound WebSocket messages from service agents on restaurant devices

#### Environment Variables
| Variable | Description |
|---|---|
| `TABLE_NAME` | DynamoDB WebSocket connections table |
| `RESULTS_TABLE_NAME` | DynamoDB script results table |
| `STAGE_NAME` | `dev` / `nprod` / `prod` |

#### Supported Actions (via `action` field in message body)
| Action | Description |
|---|---|
| `register` | Device registers itself — upserts connection record in DynamoDB |
| `heartbeat` | Device sends keep-alive — updates `last_seen` and `status: connected`, responds with `pong` |
| `save_results` | Device sends back script execution results — written to `RESULTS_TABLE_NAME` |

#### Script Results Schema (`RESULTS_TABLE_NAME`)
| Field | Description |
|---|---|
| `restaurant_number` | PK |
| `result_id` | = `command_id` sent in original trigger (SK) |
| `device_id` | Device that ran the script |
| `script_name` | Script that was run |
| `result_output` | stdout from script |
| `stderr` | stderr from script |
| `execution_status` | `success`, `failed`, `timeout` |
| `saved_at` | UTC ISO timestamp |

#### Result Status Logic (used by `snowfall-proactive-alerts`)
| Condition | Status |
|---|---|
| `execution_status` in `timeout/failed/error` | `error/timeout` |
| `stderr` is non-empty | `error/timeout` |
| `result_output` contains `COMPLETED SUCCESSFULLY` | `successful` |
| Otherwise | `unsuccessful` |

---

### 6. `snowfall-proactive-healing-jwt-authorizer`
**File:** `scripts/python/snowfall-proactive-healing-jwt-authorizer/lambda_function.py`
**Trigger:** WebSocket API Gateway — Lambda authorizer (runs before `$connect`)
**Purpose:** Validates JWT token from service agent before allowing WebSocket connection

#### Environment Variables
| Variable | Description |
|---|---|
| `TARGET_BUCKET` | S3 bucket containing the server allowlist CSV |

#### Secrets Manager
- Secret: `uk-snowfall-service-agent`
- Key: `uk-snowfall-service-agent-key` (JWT signing secret)

#### Behaviour
1. Reads `Authorization: Bearer <token>` header
2. Validates JWT signature using secret from Secrets Manager
3. Validates `machine` claim against allowlist CSV from S3 (`server_list/List of Restaurant Servers.csv`)
4. Extracts `restaurant_number`, `device_id`, `machine` from JWT claims
5. Returns IAM policy (`Allow` or `Deny`) with authorizer context injected for `$connect` Lambda

#### S3 CSV Format
```csv
server_name
UKREST-1234-PC01
UKREST-5678-PC01
```

#### JWT Algorithm
- `HS256`

---

### 7. `snowfall-proactive-healing-monitor`
**File:** `scripts/python/snowfall-proactive-healing-monitor/lambda_function.py`
**Trigger:** EventBridge scheduled rule
**Purpose:** Identifies stale or disconnected WebSocket connections for monitoring/cleanup

#### Environment Variables
| Variable | Description |
|---|---|
| `TABLE_NAME` | DynamoDB WebSocket connections table |
| `STALE_TIMEOUT` | Time before a connection is considered stale. Supports `30` (minutes), `45m`, `1h`. Default: `1h` |

#### Behaviour
- Scans connections table for records where:
  - `status = disconnected`, OR
  - `last_seen < (now - STALE_TIMEOUT)`
- Logs stale records — **does not delete them**
- Currently read-only / observability only. Future use: trigger alerts or cleanup.

---

## DynamoDB Tables Summary

| Table | Purpose | PK | SK |
|---|---|---|---|
| `RULES_TABLE` | Alert rule definitions | `rule_id` | — |
| `PROACTIVE_ALERTS_TABLE` | Alert history + cooldown tracking | `alert_id` | — |
| `TABLE_NAME` (connections) | WebSocket device connections | `restaurant_number` | `device_id` |
| `RESULTS_TABLE_NAME` | Proactive script execution results | `restaurant_number` | `result_id` |

---

## Adding a New Feature — Developer Guide

### Add a new alert rule
1. Go to DynamoDB → `RULES_TABLE`
2. Create a new item with the rule schema above
3. Set `active: true`, write the Athena SQL query, set `email_dl`, `incident_description`, `email_cooldown_hours`
4. Set `email_alert`, `proactive_script`, `servicenow_alert` flags as needed
5. No code change or deployment required

### Add a new script that runs on devices
1. Add the script to the service agent on the target devices
2. Set `proactive_script: true` and `proactive_script_name: "<script_name>"` on the rule
3. The `snowfall-proactive-alerts` Lambda sends `{ action: "trigger_script", script_name: "<script_name>" }` via WebSocket
4. The service agent runs the script and sends back results via `save_results` action
5. Results appear in the email under "Proactive Script Results"
6. Result is `successful` only if stdout contains `COMPLETED SUCCESSFULLY`

### Add a new message action in the service agent
1. Add handling in `snowfall-proactive-healing-default/lambda_function.py` under a new `elif action == "..."` block
2. Read fields from the `body` dict
3. Write to DynamoDB or respond via `apigw.post_to_connection`

### Add NCR/ServiceNow ticket creation (future)
- `servicenow_alert` flag already exists on each rule (currently unused)
- `RECORD_TYPE_SERVICENOW_CASE = "SERVICENOW_CASE"` already defined in `snowfall-proactive-alerts`
- Add `create_ncr_ticket(rule, records)` function and call it in `process_rule()` after the cooldown check
- Write a `SERVICENOW_CASE` record to `PROACTIVE_ALERTS_TABLE` with `ncr_transaction_id`, `ncr_ticket_id` etc.

### Add a new environment / stage
1. Add the WebSocket endpoint URL to the `STAGE_NAME` if/elif blocks in:
   - `snowfall-proactive-alerts/lambda_function.py` → `run_proactive_script()`
   - `snowfall-proactive-healing-default/lambda_function.py` → `lambda_handler()`
2. Add the new `STAGE_NAME` value to Terraform `variables.tf` and `tfvars` files

---

## Known Issues / Notes

| Item | Status | Detail |
|---|---|---|
| `disconnect` uses `scan` by `connectionId` | ⚠️ Open | Not ideal at scale — consider adding a GSI on `connectionId` |
| `poll_script_results` uses `scan` | ⚠️ Open | Should be replaced with a `query` once GSI or correct key structure is confirmed |
| `last_seen` uses `datetime.utcnow()` in disconnect/default | 🔵 Won't Fix | `connect` fixed (19 Apr 2026) — disconnect/default left as-is, both are working in production |
| `servicenow_alert` flag | ⚠️ Open | Present on all rules but not yet implemented — placeholder for NCR integration |
| WebSocket API endpoint URLs | ⚠️ Open | Hardcoded in two Lambda files — should be driven by `WEBSOCKET_ENDPOINT` env var |
| `healing-connect`: stale query param code + unused `params` variable | ✅ Fixed (19 Apr 2026) | Removed dead code block — credentials now read exclusively from JWT authorizer context |
| `healing-connect`: `datetime.utcnow()` | ✅ Fixed (19 Apr 2026) | Replaced with `datetime.now(timezone.utc)` |
| `healing-connect`: `print(event)` logging full event | ✅ Fixed (19 Apr 2026) | Replaced with targeted log: `connection_id`, `restaurant`, `device` only |
| `healing-connect`: `put_item` unhandled exception | ✅ Fixed (19 Apr 2026) | Wrapped in try/except — returns clean 500 on DynamoDB failure |
