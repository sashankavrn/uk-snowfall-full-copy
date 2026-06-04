# NCR ServiceNow Integration – Task List

Last updated: 2026-06-04

## Tasks

- TASK-1: Fix CLOSING state bug
	Status: Done
	Why: Case stuck in CLOSING forever, blocking new ticket creation.

- TASK-2: Fix ATHENA_VIEW default
	Status: Done
	Why: Wrong database causing Athena queries to fail.

- TASK-3: Test create-ticket Lambda
	Status: Done
	Why: Core flow must create NCR ticket from proactive alert.

- TASK-4: Test close-ticket Lambda end to end
	Status: In progress
	Why: Close payload is now aligned with working Postman request, but Lambda still needs runtime verification against a real open ticket flow.

- TASK-5: Fix IE CountryCode (7000+)
	Status: Done
	Why: Implemented rule `< 7000 -> UK`, `>= 7000 -> IE` and pushed to dev.

- TASK-6: E2E lifecycle test
	Status: Not done
	Why: Full flow sign-off gate for CERT approval: alert fires, ticket is created, condition clears, ticket is closed.

- TASK-7: Script attempt dedup
	Status: Not done
	Why: Same script could be sent twice to the same device in one run when multiple WebSocket connections exist. Previous fix was lost in the June 3 revert.

- TASK-8: Immediate close on script success
	Status: Not done
	Why: If a proactive script fixes the issue, the ticket should close immediately instead of waiting for the next Athena cycle.

- TASK-9: Confirm SOURCE_SYSTEM with NCR
	Status: Not done
	Why: We send `WS`, while NCR sample payloads use `CUSTOMERAPP`. This could matter in PROD.

- TASK-10: Move NCR URLs to tfvars by environment
	Status: Done
	Why: CERT/PROD endpoints should be config values, not secret-only or static values. Wired through `dev.tfvars`.

- TASK-11: Align schedule with diagram
	Status: Deferred
	Why: Dev uses 5 minutes while the doc says 30 minutes. Left intentionally for dev testing.

---

## Known Bugs

- `site_number` over-padding
	Fixed: Yes
	Detail: Athena stored `04071`, and `zfill(4)` kept it at 5 digits. Fix was `str(int(site_number)).zfill(4)`.

- `CountryCode: IE` for 7000+
	Fixed: Yes
	Detail: Final rule is now `< 7000 -> UK`, `>= 7000 -> IE`.

- `dry_run` bool in cleanup Lambda
	Fixed: Yes
	Detail: `bool("false")` is `True` in Python, so cleanup never deleted. Fixed with `_coerce_bool()`.

- `proactive_script_name` KeyError
	Fixed: Yes
	Detail: `rule["proactive_script_name"]` crashed when the key was missing. Fixed to `rule.get(...)`.

- Cleanup lambda skipped FAILED rows
	Fixed: Yes
	Detail: Cleanup behavior was hardened so the default delete-all path removes all ticket rows, including FAILED items.

- Close lambda payload mismatch
	Fixed: Yes
	Detail: Close payload now matches the successful Postman request: `CustomerTicketID` is alert/customer id, `TicketID` is NCR ticket id, country code is dynamic, and resolution note is updated.

---

## NCR CERT Endpoints

- Create ticket: `https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest`
- Update/Close ticket: `https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/UpdateServiceRequest`

- Auth: HTTP Basic Auth (`Authorization: Basic <base64>`)
- Credentials: stored in Secrets Manager `uk-snowfall-ncr-servicenow`
- URLs: now supplied via Terraform tfvars (`ncr_soap_service_now_create_url`, `ncr_soap_service_now_update_url`)
- SSL verify: `false` (NCR CERT uses private CA)

---

## Lambda Stack

- `snowfall-proactive-alerts`: Orchestrator. Runs Athena, sends email, triggers ticket create/close.
- `servicenow-proactive-ticket-creation`: Sends `CreateServiceRequest` to NCR and saves result to DynamoDB.
- `servicenow-proactive-ticket-close`: Sends `UpdateServiceRequest` to NCR to close/resolve a ticket.
- `servicenow-proactive-ticket-sync`: Reconciles ticket statuses using Athena.
- `servicenow-tickets-cleanup`: Bulk-deletes old rows from the `service-now-tickets` DynamoDB table.

---

## Pending NCR Confirmations

- [ ] PROD endpoint URL
- [ ] Confirm `SourceSystem` value NCR expects (`WS` vs `CUSTOMERAPP`)
- [ ] PROD credentials
