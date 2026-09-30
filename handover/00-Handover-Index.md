# UK Snowfall Data Pipeline — Lambda Handover Documentation

I'm handing over the Snowfall platform, so this is my attempt to write down everything I'd otherwise just tell you over a coffee. It covers all 30 Lambda functions in `uk-snowfall-data-pipeline` (`core_delta_lake` + `datashare_resources`). The ThousandEyes webhook processor and its authorizer are gone as of this handover, so they're not covered here.

McDonald's UK Snowfall Data Platform. AWS, Terraform, `eu-central-1`.

---

## What Snowfall actually does, in plain English

If you're not an engineer: Snowfall watches the IT in McDonald's UK restaurants (tills, kiosks, back-office servers, network kit) using data pulled from Meraki, New Relic and, previously, ThousandEyes. When something looks wrong it can do up to three things on its own: email the ops team, push a fix script straight down to the restaurant's PC, and raise a ticket with NCR's service desk. Nobody has to spot the problem first. There's also a "datashare" side that copies some of this data out to other McDonald's teams like Tech360.

The nice part for whoever inherits this: almost everything is config, not code. New alert rules are just rows in a DynamoDB table. And it's all serverless Lambda, so there's no box to patch.

---

## How I've laid this out

I split it into one page per functional area rather than one giant wall of text, because in practice you'll be looking for "the NCR ticket one" or "the New Relic ones", not scrolling an alphabetical list of 30 headings. If you're moving this into Confluence: make this file the parent page, each of the 9 files below a child page, and keep the same shape inside each Lambda's section — a short metadata line (trigger/source path/AWS name), then what it does, then how it works plus any gotchas. Tag the pages (`snowfall`, `lambda`, `ncr`, `newrelic`, whatever fits your space) so they turn up in search.

---

## Group pages

| # | Page | Lambdas covered |
|---|---|---|
| 1 | [01-Snowfall-Proactive-Alerts-and-Device-Healing.md](01-Snowfall-Proactive-Alerts-and-Device-Healing.md) | Orchestrator, rule seeding, WebSocket connect/disconnect/default/monitor/JWT authorizer (7) |
| 2 | [02-ServiceNow-NCR-Ticketing.md](02-ServiceNow-NCR-Ticketing.md) | Ticket create, close, sync, cleanup utility (4) |
| 3 | [04-NewRelic-RMP-Monitoring.md](04-NewRelic-RMP-Monitoring.md) | RMP device/network/process metrics collectors (5) |
| 4 | [05-NewRelic-Digital-FOE-Response.md](05-NewRelic-Digital-FOE-Response.md) | Digital 3PO/GMA front-of-house response collectors (2) |
| 5 | [06-Meraki-Network-Inventory.md](06-Meraki-Network-Inventory.md) | Meraki device & client inventory collectors (2) |
| 6 | [07-Service-Agent-Integration.md](07-Service-Agent-Integration.md) | Restaurant device agent upload/auth/file-copy/server-list (4) |
| 7 | [08-Core-Data-Platform-Utilities.md](08-Core-Data-Platform-Utilities.md) | Landing trigger, Athena view creation, ODS/Smartsheet feeds (4) |
| 8 | [09-Datashare-Resources.md](09-Datashare-Resources.md) | Datashare landing/processed sync Lambdas (2) |

That's 30 Lambdas in total, across 8 groups, numbered 1-8 above for readability. The filenames themselves still jump from `02-` to `04-` — that gap is where the ThousandEyes doc used to live before it was decommissioned, and I left it retired rather than renumbering every file. So group 3 in this list is the file named `04-...`, group 4 is `05-...`, and so on one off from the filename — a bit annoying, but less risky than renaming files and breaking every link into this set.

One more page outside the numbered groups: [10-Lessons-Learned-and-Troubleshooting-History.md](10-Lessons-Learned-and-Troubleshooting-History.md) — debugging history and context that isn't written down anywhere else (the HARD/SOFT cooldown saga, NCR API integration gotchas, the meraki fix). Worth reading once before you dig into anything that seems weird.

---

## Architecture Overview

```
Source APIs (Meraki, New Relic, Smartsheet, NCR ServiceNow via AppFlow)
        │
        ▼
  Landing S3 bucket  ──►  landing_trigger Lambda  ──►  Raw S3 bucket (per dataset)
        │
        ▼
  EventBridge (S3 object-created) ──► Glue workflows ──► Delta Lake (prep/processed/semantic)
        │
        ▼
  Athena (query layer) ──► create_athena_views Lambda (builds views from SQL files in S3)
        │
        ├──► Datashare Lambdas (datashare_landing_trigger / datashare_processed_trigger) → Tech360 & datashare buckets
        │
        └──► Snowfall Proactive Alerts orchestrator (EventBridge, every 5 min)
                   ├─► Athena rule queries → email alerts (Mailjet SMTP)
                   ├─► WebSocket API → Service Agent (device scripts) → healing-default/connect/disconnect/monitor
                   └─► ServiceNow/NCR ticket create/close Lambdas (async invoke) → ticket-sync reconciles nightly against NCR Athena view
```

## Key shared AWS resources (cross-cutting — useful for on-call triage)

| Resource | Used by |
|---|---|
| Secrets Manager secret `uk-snowfall` | New Relic, Meraki, Mailjet SMTP creds |
| Secrets Manager secret `uk-snowfall-service-agent` | Service agent / proactive-healing JWT signing key |
| Secrets Manager secret `uk-snowfall-ncr-servicenow` | NCR REST API Basic Auth credentials |
| DynamoDB `uk-snowfall-<env>-incident-rules` | Proactive alert rule definitions |
| DynamoDB `uk-snowfall-<env>-proactive-alerts` | Alert/case history (`EMAIL_ALERT` / `SERVICENOW_CASE` record types) |
| DynamoDB `uk-snowfall-<env>-service-now-tickets` | NCR ticket records (create/close/sync) |
| DynamoDB `uk-snowfall-<env>-proactive-websocket-connections` | Connected restaurant device WebSocket sessions |
| Athena view `uk_snowfall_semantic.ncr_service_now_service_case_latest` | NCR ticket close-sync reconciliation |
| SNS topic (`SNS_TOPIC_ARN`) | Operational failure notifications, used by nearly every Lambda |

## Environments
`dev` / `nprod` / `prod` — driven by Terraform `var.environment` / `var.stage_name` and the corresponding `.tfvars` file in `terraform/`. Note: NCR's own `service_case` data feed to our DEV Athena view was intentionally stopped by NCR — DEV ticket close-sync testing must cross-read PROD data (see [02-ServiceNow-NCR-Ticketing.md](02-ServiceNow-NCR-Ticketing.md)).

## Where to look for more detail
- `Localfiles/snowfall-docs/snowfall-proactive-lambdas-reference.md` — deep technical reference for the proactive-alerts/healing family (env vars, DynamoDB schemas, dev guide for adding rules/scripts).
- `Localfiles/snowfall-docs/ncr-ticket-creation-lambda-engineering.md` and `ncr-voyix-integration-summary.md` — NCR REST API integration notes.

---

## Glossary

| Term | Meaning |
|---|---|
| RMP | Restaurant Management Platform — the in-restaurant back-office servers/tills monitored by New Relic (Group 3) |
| FOE | Front Of Establishment — customer-facing digital estate (kiosks, menu boards) monitored via New Relic "3PO"/"GMA" accounts (Group 4) |
| NCR / NCR Voyix | McDonald's UK's external service-desk provider; tickets raised here show up in their ServiceNow instance |
| Service Agent | Windows service running on restaurant back-office PCs that uploads diagnostic files and holds a WebSocket connection for remote script execution |
| Proactive alert rule | A DynamoDB row in `incident-rules` defining an Athena query, cooldown behaviour, and what to do (email/script/NCR ticket) when it returns rows |
| Cooldown (`cooldown_type`) | Per-rule throttle on repeat email alerts — `SOFT` (time-based, resets early on new restaurants) or `HARD` (first alert only, then permanently suppressed) |
| SERVICENOW_CASE / EMAIL_ALERT | The two `record_type` values used to discriminate rows in the shared `proactive-alerts` DynamoDB table |
| Datashare | The distribution layer (separate `datashare_resources` Terraform module) that republishes processed data to other teams, e.g. Tech360 |
| Landing bucket | The first S3 bucket any external/scheduled dataset lands in before `landing_trigger` routes it to its dataset-specific raw location |

## Known gaps — status tracker

| Gap | Status | Notes |
|---|---|---|
| `servicenow-proactive-ticket-creation` / `-close` source missing locally | ✅ Resolved (2026-09-21) | Source now present in repo checkout; Group 2 doc verified against it |
| `dynamic-smartsheet-intergation` source missing locally | ✅ Resolved (2026-09-21) | Source now present; Group 7 doc updated with verified details |
| `meraki-client-info` `notify_failure()` disabled by stray early `return` | ✅ Fixed (2026-09-21) | Dead `return` removed; SNS failure alerts for this Lambda now fire again |
| `ods-user-data-to-datashare` S3 trigger commented out in Terraform | ⚠️ Still open | Intentionally left as-is — re-enabling changes live S3 event wiring and needs a deliberate decision/PR, not a doc-only fix. See Group 7 runbook. |

---

## Your first week

A few honest suggestions rather than a formal checklist. Get access sorted first: the `dev` AWS account at minimum, read access to the `uk-snowfall`, `uk-snowfall-service-agent` and `uk-snowfall-ncr-servicenow` secrets, and the `uk-snowfall-data-pipeline` repo.

Then, rather than reading everything cover to cover, I'd start with Group 1 and Group 2 — that's the proactive alerts → NCR ticket flow, and it's the one you'll get paged about most. Go find `snowfall-proactive-alerts-orchestrator` in CloudWatch and read through one recent log stream so you can see a rule evaluation actually happen. Open the `incident-rules` table and look at a couple of real rule items — it'll make `cooldown_type` and the various `*_alert`/`proactive_script` flags click in a way that reading about them never quite does.

After that, keep each group's Troubleshooting/Runbook table bookmarked somewhere handy — that's genuinely the fastest way to get oriented when a real incident lands on your desk. And one thing I'll flag directly rather than bury in a table: the `ods-user-data-to-datashare` trigger is currently disabled in Terraform (see below). Don't just flip it back on because it looks like an oversight — raise it with the team first, since it changes live S3 event wiring.

## Questions people keep asking me

**Does changing an alert rule need a deployment?**
No. Rules are rows in the `incident-rules` DynamoDB table, so adding or editing one is just a config change.

**NCR said the ticket was created but we can't find it — what gives?**
NCR's API returns HTTP 200 even when the request actually failed, so you have to check `Header.Status`/`Fault.FaultCode` in the response body rather than trusting the status code. More detail in the [Group 2 runbook](02-ServiceNow-NCR-Ticketing.md#troubleshooting--runbook).

**Does Snowfall just alert, or can it actually fix things?**
Both, if the rule has a `proactive_script` configured — the orchestrator can push a script down to the restaurant's device over WebSocket and wait for the result, on top of emailing or ticketing.

**What happens if New Relic or Meraki has an outage?**
Not much — each collector runs on its own schedule and reports failures to SNS independently (apart from `dynamic-smartsheet-intergation`, which currently only logs failures rather than alerting — see Group 7). One source being down for a bit doesn't take anything else with it.

**I think something in this doc is wrong — what do I do?**
Same as you'd treat a bug: check it against the actual Terraform/source first (every Lambda's metadata line tells you where to look), then fix the doc and date the correction, the same way the "Known gaps" table below does it.

---

## Appendix A: Complete Lambda inventory (all 30, one page)

| Lambda | Group | Trigger | One-line purpose |
|---|---|---|---|
| `snowfall-proactive-alerts-orchestrator` | 1 | EventBridge, 5 min | Evaluates alert rules against Athena; drives scripts, email, and NCR tickets |
| `snowfall-proactive-dynamodb-rules` | 1 | Manual | One-off bootstrap: seeds placeholder rows into `incident-rules` |
| `snowfall-proactive-healing-connect` | 1 | WebSocket `$connect` | Registers a device's WebSocket connection after JWT auth |
| `snowfall-proactive-healing-default` | 1 | WebSocket `$default` | Handles register/heartbeat/save_results messages from devices |
| `snowfall-proactive-healing-disconnect` | 1 | WebSocket `$disconnect` | Marks a device's connection record disconnected |
| `snowfall-proactive-healing-jwt-authorizer` | 1 | WebSocket authorizer | Validates device JWT + server allow-list before connect |
| `snowfall-proactive-healing-monitor` | 1 | EventBridge | Read-only: logs stale/disconnected device connections |
| `servicenow-proactive-ticket-creation` | 2 | Async invoke (orchestrator) | Creates an NCR ServiceNow ticket for a violation |
| `servicenow-proactive-ticket-close` | 2 | Async invoke (orchestrator) | Resolves/closes an NCR ticket once the issue clears |
| `servicenow-proactive-ticket-sync` | 2 | EventBridge, hourly | Reconciles tickets NCR closed on their own side |
| `servicenow-tickets-cleanup` | 2 | Manual | DEV utility to bulk-delete test ticket/alert rows |
| `newrelic-rmp-device-metrics` | 3 | EventBridge, 10 min | Device disk/CPU metrics; feeds the proactive disk-space rule |
| `newrelic-rmp-fetch-device` | 3 | EventBridge, hourly | Device/OS inventory metadata |
| `newrelic-rmp-network-info` | 3 | EventBridge, 10 min | Per-interface network telemetry (high frequency) |
| `newrelic-rmp-network-info-daily-aggregate` | 3 | EventBridge, daily | Daily-aggregated network telemetry rollup |
| `newrelic-rmp-process-info` | 3 | EventBridge, 10 min | Running-process visibility per host |
| `newrelic-digital-3po-foe-response` | 4 | EventBridge, hourly | 3PO digital front-of-house response metrics |
| `newrelic-digital-gma-foe-response` | 4 | EventBridge, hourly | GMA digital front-of-house response metrics |
| `meraki-client-info` | 5 | EventBridge, ~1 min (self-recursive) | Connected client/device inventory per network |
| `meraki-fetch-device` | 5 | EventBridge, ~1 min | Meraki hardware (AP/switch) inventory |
| `service-agent-server-files` | 6 | S3 event | Copies service-agent uploads to a stable prefix; supports verify/backfill |
| `service-agent-server-list-extract` | 6 | EventBridge, daily 01:30 | Builds the restaurant-server allow-list CSV from Athena |
| `service-agent-upload-s3` | 6 | API Gateway REST | Upload endpoint for service-agent diagnostic files |
| `service-agent-upload-s3-jwt-authorizer` | 6 | API Gateway authorizer | Validates JWT + allow-list for uploads |
| `create_athena_views` | 7 | S3 event | Deploys/updates Athena views from uploaded SQL files |
| `landing_trigger` | 7 | S3 event | Central router: lands files into the correct raw-bucket per `mapping.json` |
| `ods-user-data-to-datashare` | 7 | S3 event (currently disabled) | Moves ODS user-data CSVs onward to datashare (Sopra → NCR) |
| `dynamic-smartsheet-intergation` | 7 | EventBridge, daily 06:00 | Pulls 2 hard-coded Smartsheet sheets into the landing bucket |
| `datashare_landing_trigger` | 8 | EventBridge, hourly `:30` | Fans out landing-bucket data to datashare + Tech360 buckets |
| `datashare_processed_trigger` | 8 | EventBridge, 5 min + S3 event | Diff-syncs processed-bucket folders to the datashare bucket |

---

**Status: ready for handover.** I did a final pass on 2026-09-27 and re-checked the two things most likely to go stale — the `meraki-client-info` schedule (Terraform still says "STOPPED FOR NOW", unchanged) and the `ods-user-data-to-datashare` trigger (still commented out in Terraform, unchanged) — both are as documented below. The "Known gaps" table is the honest list of what's still open; everything else in this set has been checked directly against the Terraform/Lambda source. Worth another pass next time there's a major change to `core_delta_lake` or `datashare_resources`, or if it's been a good few months.
- `terraform/core_delta_lake/lambda/main.tf` and `terraform/datashare_resources/lambda/main.tf` — authoritative source for triggers, schedules, env vars and IAM wiring for every Lambda (source of truth if this doc and the code ever disagree).
