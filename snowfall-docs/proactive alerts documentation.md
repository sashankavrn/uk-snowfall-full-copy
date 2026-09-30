# Snowfall Proactive Alerts — Technical Documentation

**Project:** Proactive Alerts
**Client:** McDonald’s UK
**Platform:** AWS Lambda + ServiceNow (NCR Voyix)
**Status:** Pre-implementation

-----

## Overview

The Proactive Alerts system automatically detects violations in McDonald’s UK restaurant data, attempts automated remediation via the Snowfall Agent installed on store PCs, and manages the full ServiceNow ticket lifecycle with NCR Voyix — all for **audit and operational visibility**.

> **Key design principle:** A ServiceNow ticket is always opened when a violation is detected, even if the Snowfall Agent fixes the issue automatically. This ensures a complete audit trail of every incident.

-----

## Architecture

The system is composed of 4 AWS Lambda functions:

|Lambda|Name                   |Role                                                                            |
|------|-----------------------|--------------------------------------------------------------------------------|
|λ4    |`alerts` (Orchestrator)|Main engine — runs rules, triggers scripts, emails, opens/closes tickets        |
|λ1    |`create-ticket`        |Creates a ServiceNow ticket in NCR Voyix via CSDI API                           |
|λ2    |`close-ticket`         |Resolves a ServiceNow ticket in NCR Voyix                                       |
|λ3    |`close-sync`           |Background reconciler — syncs DynamoDB with NCR-side closures from data pipeline|

-----

## Lambda 4 — Alerts Orchestrator

### Trigger

AWS EventBridge timer — runs every **30 minutes**.

### What it does

Scans all active rules stored in DynamoDB and processes each one in sequence.

#### Step 1 — Run Athena Query

Executes the rule’s SQL query against the `uk_snowfall_processed` Athena database to detect current violations. Each result row contains a `restaurant_number` and a `message` describing the violation.

#### Step 2 — No Violations?

If Athena returns no rows and the rule has `servicenow_alert = true`:

- Checks if there is an open ServiceNow case for this rule
- If yes → invokes **λ2** asynchronously to close the ticket
- Updates the case record to `CLOSING` in DynamoDB

#### Step 3 — Run Proactive Script (if `proactive_script = true`)

For each affected restaurant:

- Sends the script command via **WebSocket** to the **Snowfall Agent** installed on store PCs
- Polls for the result for up to **30 seconds**
- Collects script output (successful / unsuccessful / error/timeout)

The Proactive Agent is installed on all PCs across McDonald’s UK restaurants and executes scripts locally, reporting results back over the WebSocket connection.

#### Step 4 — Cooldown Check

Before sending any alert, checks the alert history in DynamoDB:

- If the same restaurants were alerted within the cooldown window → **skip**
- If a **new restaurant** appears in the violations → **bypass cooldown** and alert immediately
- Cooldown duration is configurable per rule via `email_cooldown_hours`

#### Step 5 — Send Email (if `email_alert = true`)

Sends an HTML email via **Mailjet SMTP** to the distribution list configured on the rule (`email_dl`). The email includes:

- Violation count and rule description
- Table of affected restaurants and violation messages
- Proactive script results (if a script was run)

#### Step 6 — Record Alert

Always writes an `EMAIL_ALERT` record to the `proactive-alerts` DynamoDB table, regardless of whether the email was sent. Status is `SENT` or `RECORDED`.

#### Step 7 — Open ServiceNow Ticket (if `servicenow_alert = true`)

- Checks if an `OPEN` `SERVICENOW_CASE` already exists for this rule → if yes, skips
- If no open case → writes a `SERVICENOW_CASE` record (status: `OPEN`) to DynamoDB
- Asynchronously invokes **λ1** to create the ticket in NCR Voyix

> **Note:** The ticket is raised even if the proactive script successfully fixed the issue. This is intentional — for **audit purposes**.

-----

### Rule Flags (DynamoDB `incident-rules` table)

|Flag                   |Type   |Description                                               |
|-----------------------|-------|----------------------------------------------------------|
|`active`               |Boolean|Whether the rule is evaluated each run                    |
|`proactive_script`     |Boolean|Whether to run a remediation script on affected stores    |
|`proactive_script_name`|String |Name of the script to send to the Snowfall Agent          |
|`email_alert`          |Boolean|Whether to send an email notification                     |
|`email_dl`             |String |Comma or semicolon-separated recipient email addresses    |
|`email_cooldown_hours` |Number |Minimum hours between repeated alerts for same restaurants|
|`servicenow_alert`     |Boolean|Whether to open/close a ServiceNow ticket                 |
|`query`                |String |Athena SQL query to detect violations                     |

-----

## Lambda 1 — Create ServiceNow Ticket

### Trigger

Invoked **asynchronously** by λ4 when a new violation case is opened.

### What it does

1. Receives the alert and rule payload from λ4
1. Falls back to fetching the rule from DynamoDB if not provided
1. Builds a `CreateServiceRequest` JSON payload
1. POSTs to the **NCR CSDI API** using HTTP Basic Auth
1. Saves the ticket record to the `service-now-tickets` DynamoDB table
1. Writes the `ncr_ticket_id` back to the `SERVICENOW_CASE` record in `proactive-alerts` table so λ2 can find it directly

### Key fields saved to DynamoDB

`ticket_id`, `ncr_ticket_id`, `alert_id`, `rule_id`, `restaurant_number`, `status`, `category`, `subcategory`, `priority`, `service_offering`, `created_at`, `request_payload`, `response_payload`

### Country Code Logic

- Restaurant numbers **>= 7000** → country code `IE` (Ireland)
- Restaurant numbers **< 7000** → country code `UK`

-----

## Lambda 2 — Close ServiceNow Ticket

### Trigger

Invoked **asynchronously** by λ4 when Athena returns no violations for a rule that had an open case.

### What it does

1. Receives the rule and case payload
1. Resolves the NCR ticket ID — from the case record directly, or by scanning `service-now-tickets` by `source_alert_id`
1. If no NCR ticket ID found (ticket never created or still in-flight) → marks case `CLOSED` with status `SKIPPED`, exits gracefully
1. Builds a `ResolveServiceRequest` payload
1. POSTs to the **NCR CSDI Resolve endpoint**
1. Updates `service-now-tickets`: sets `resolved_at`, `ncr_close_status`, `close_notes`
1. Updates `proactive-alerts` case record: status → `CLOSED`

-----

## Lambda 3 — Close Sync (Background Reconciler)

### Trigger

Scheduled independently (separate from the 30-minute main flow).

### Why it exists

λ2 closes tickets that **Snowfall initiates**. However, NCR engineers may close tickets manually in ServiceNow, or closures may happen via NCR’s own workflows. λ3 catches these **external closures** and syncs them back into DynamoDB to keep the ticket inventory accurate.

### Data source

NCR ServiceNow data flows into the system via a **data pipeline** and is exposed as an Athena view:

```
uk_snowfall_semantic.ncr_service_now_service_case_latest
```

### What it does

1. Scans `service-now-tickets` for open tickets (`status = SUCCESS`, no `closed_at`)
1. Batches NCR case numbers (default: 100 per batch, max 500 per run)
1. Queries the Athena view for any rows with `state IN ('Closed', 'Resolved')` for those case numbers
1. For each closed/resolved row → updates DynamoDB ticket record with:
- `closed_at`, `ncr_state`, `close_notes`, `resolution_code`, `resolved_at`, `close_synced_at`
1. Logs summary: `checked / closed / batches`

-----

## DynamoDB Tables

|Table                                  |Purpose                                                    |
|---------------------------------------|-----------------------------------------------------------|
|`uk-snowfall-<env>-incident-rules`     |Rule definitions and flags                                 |
|`uk-snowfall-<env>-proactive-alerts`   |Alert history (`EMAIL_ALERT` and `SERVICENOW_CASE` records)|
|`uk-snowfall-<env>-service-now-tickets`|ServiceNow ticket inventory                                |
|`uk-snowfall-<env>-connections`        |Active WebSocket connections per restaurant                |
|`uk-snowfall-<env>-results`            |Proactive script execution results                         |

-----

## External Integrations

|Service                        |Purpose                                            |
|-------------------------------|---------------------------------------------------|
|**NCR Voyix CSDI API**         |Create and resolve ServiceNow tickets              |
|**Mailjet SMTP**               |Send violation alert emails                        |
|**Snowfall Agent (WebSocket)** |Run remediation scripts on restaurant PCs          |
|**AWS Athena**                 |Query processed violation data and NCR ticket views|
|**AWS Secrets Manager**        |Store NCR API credentials and SMTP keys            |
|**AWS API Gateway (WebSocket)**|Manage connections to Snowfall Agents              |

-----

## Environment Variables

### λ4 (Alerts Orchestrator)

|Variable                  |Description                                           |
|--------------------------|------------------------------------------------------|
|`RULES_TABLE`             |DynamoDB rules table name                             |
|`PROACTIVE_ALERTS_TABLE`  |DynamoDB proactive alerts table name                  |
|`TABLE_NAME`              |DynamoDB WebSocket connections table                  |
|`RESULTS_TABLE_NAME`      |DynamoDB script results table                         |
|`ATHENA_OUTPUT_S3`        |S3 path for Athena query results                      |
|`STAGE_NAME`              |`dev` / `nprod` / `prod` — controls WebSocket endpoint|
|`SERVICENOW_TICKET_LAMBDA`|ARN/name of λ1                                        |
|`SERVICENOW_CLOSE_LAMBDA` |ARN/name of λ2                                        |

### λ1 (Create Ticket)

|Variable                   |Description                                                   |
|---------------------------|--------------------------------------------------------------|
|`SECRET_NAME`              |Secrets Manager secret (default: `uk-snowfall-ncr-servicenow`)|
|`SECRET_REGION`            |AWS region for secret (default: `eu-central-1`)               |
|`SERVICE_NOW_TICKETS_TABLE`|DynamoDB tickets table                                        |
|`RULES_TABLE`              |DynamoDB rules table                                          |
|`PROACTIVE_ALERTS_TABLE`   |DynamoDB alerts table (optional)                              |
|`SOURCE_SYSTEM`            |NCR source system identifier (default: `WS`)                  |
|`USER_ID`                  |NCR user ID (default: `UKMCD`)                                |
|`COUNTRY_CODE`             |Fallback country code (default: `UK`)                         |
|`NCR_VERIFY_SSL`           |SSL verification — `true`/`false` (default: `false`)          |

### λ2 (Close Ticket)

|Variable                   |Description                                                   |
|---------------------------|--------------------------------------------------------------|
|`SECRET_NAME`              |Secrets Manager secret (default: `uk-snowfall-ncr-servicenow`)|
|`SECRET_REGION`            |AWS region for secret (default: `eu-central-1`)               |
|`SERVICE_NOW_TICKETS_TABLE`|DynamoDB tickets table                                        |
|`PROACTIVE_ALERTS_TABLE`   |DynamoDB alerts table                                         |
|`SOURCE_SYSTEM`            |NCR source system identifier (default: `WS`)                  |
|`USER_ID`                  |NCR user ID (default: `UKMCD`)                                |
|`NCR_VERIFY_SSL`           |SSL verification — `true`/`false` (default: `false`)          |

### λ3 (Close Sync)

|Variable                   |Description                                                      |
|---------------------------|-----------------------------------------------------------------|
|`SERVICE_NOW_TICKETS_TABLE`|DynamoDB tickets table                                           |
|`ATHENA_OUTPUT_S3`         |S3 path for Athena query results                                 |
|`ATHENA_DATABASE`          |Athena database (default: `uk_snowfall_semantic`)                |
|`ATHENA_VIEW`              |Athena view name (default: `ncr_service_now_service_case_latest`)|
|`ATHENA_WORKGROUP`         |Athena workgroup (default: `uk-snowfall-pipeline`)               |
|`BATCH_SIZE`               |Case numbers per Athena query (default: `100`)                   |
|`MAX_TICKETS_PER_RUN`      |Safety cap on tickets processed per run (default: `500`)         |

-----

## AWS Secrets Manager

Secret name: `uk-snowfall-ncr-servicenow`

|Key                                     |Description                                                                           |
|----------------------------------------|--------------------------------------------------------------------------------------|
|`uk-snowfall-ncr-servicenow-url`        |NCR CSDI CreateServiceRequest endpoint                                                |
|`uk-snowfall-ncr-servicenow-resolve-url`|NCR CSDI ResolveServiceRequest endpoint (optional — derived from create URL if absent)|
|`uk-snowfall-ncr-servicenow-username`   |NCR API username                                                                      |
|`uk-snowfall-ncr-servicenow-password`   |NCR API password                                                                      |

Secret name: `uk-snowfall`

|Key                                    |Description          |
|---------------------------------------|---------------------|
|`uk-snowfall-proactive-smpt-api-key`   |Mailjet SMTP username|
|`uk-snowfall-proactive-smpt-secret-key`|Mailjet SMTP password|

-----

*Documentation generated from source code review — June 2026*