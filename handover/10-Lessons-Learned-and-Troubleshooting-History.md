# Lessons Learned & Troubleshooting History

This one isn't a "how the system works" doc like the other 8 — it's the debugging history and hard-won context that doesn't show up anywhere else in the codebase or Terraform. If you're picking this project up, read this before you re-investigate something that's already been chased down before.

---

## Proactive alerts: HARD vs SOFT email cooldown (`should_send_alert()`)

File: `terraform/core_delta_lake/lambda/scripts/python/snowfall-proactive-alerts-orchestrator/lambda_function.py`

**Current behaviour (as of 2026-09-29, confirmed final for now):**
- `cooldown_type` blank → no cooldown check at all, always sends.
- First alert ever for a rule always sends, regardless of HARD/SOFT.
- **SOFT**: waits out `email_cooldown_hours`, but bypasses the wait early if a *new* restaurant starts violating that wasn't in the last alert.
- **HARD**: ignores restaurant/result changes entirely, but resends once `email_cooldown_hours` has genuinely elapsed since the last `SENT` alert. If `email_cooldown_hours` is 0/blank on a HARD rule, it never repeats (this is deliberate, not a bug — see history below).

**This flip-flopped twice before landing here — don't re-litigate it without re-confirming with whoever owns the rules now:**
1. A time-based HARD resend was tried first (per a pasted spec). It turned out rules were re-alerting immediately, not after a real cooldown.
2. Root cause: a `cooldown_hours <= 0` short-circuit was running *before* the HARD check, and the rule's `cooldown_hours` was 0 — so it bypassed suppression entirely. Fix at the time was to make HARD permanently suppress after the first alert, full stop, no time-based resend ever.
3. On 2026-09-29 the "permanent suppression" behaviour was explicitly reversed back to time-based resend, on request — this time with `cooldown_hours <= 0` correctly mapped to "never repeat" for HARD (not "always allow", which is what SOFT does), so the original bug can't recur.
4. **Gotcha**: a `git pull` mid-session silently reverted this exact function back to the old permanent-suppression version once already. If this function's behaviour looks wrong, re-read the actual current file content before assuming what you remember is what's deployed — don't trust a description of past changes over the live code.

`test_cooldown.py` in the same folder covers this logic — keep it in sync if `should_send_alert()` changes again.

---

## NCR Service Desk API — integration notes

Source: NCR's technical doc + a working Postman collection they provided for CERT connectivity testing. The old tech doc describes SOAP; the real interface is REST JSON.

- **Protocol**: REST JSON over HTTPS, not SOAP. Auth is HTTP Basic (username + password), not WS-Security or mTLS — confirmed on CERT.
- **CERT endpoint**: `https://osbcert-ha.ncrvoyix.com/ext/CSDI/HSRStandardSyncRestReq/ServiceRequest/CreateServiceRequest`. PROD endpoint TBC at time of writing.
- The CERT credential used in testing (`MA230518`) is NCR's own shared sample credential, **not** our dedicated account — NCR still owed us dedicated CERT/PROD credentials as of last check.
- `Site.SiteNumber` = UK restaurant number, **zero-padded to 4 digits** (e.g. `59` → `"0059"`).
- **`ServiceOffering`/`Category`/`Subcategory` must match one of NCR's pre-approved combinations** — it's validated as a set, not freeform. Confirmed combos: `(KVS Zero / Connectivity / Other)`, `(RFM / Menu Item Issues / Item Missing)`, `(Kiosk / Software / Other)`. New classification values were rejected by NCR — a ticket was raised with them and is parked/blocked as of last check.
- **HTTP 200 is returned even on business-logic failure** — always check `Header.Status` / `Header.Fault.FaultCode` / `FaultDescription` in the body, never trust the status code alone.
- The full `IncidentUpdate` (ticket ID, status, logistics) comes back **synchronously** in the create response — no need to wait for an async callback for the initial ticket data.
- Outbound lifecycle callbacks (NCR → us, e.g. Dispatched/Closed) use **Basic Auth** too, confirmed — no client certificate required.
- Rules table columns are lowercase: `servicenow_category`, `servicenow_service_offering`, `servicenow_subcategory`. A sample rule was once created with `servicenow_Subcategory` (capital S) which the create Lambda's lowercase-only field read silently ignored — worth double-checking casing if a new rule's NCR fields aren't mapping.

Full engineering detail: [snowfall-docs/ncr-ticket-creation-lambda-engineering.md](../snowfall-docs/ncr-ticket-creation-lambda-engineering.md) and [snowfall-docs/jira-ncr-integration-epic.md](../snowfall-docs/jira-ncr-integration-epic.md).

---

## NCR `service_case` data: DEV is stale by design, use PROD

- DEV's NCR `service_case` ingest was **intentionally stopped** (confirmed by the team, 2026-05-11) — DEV's Athena view `uk_snowfall_semantic.ncr_service_now_service_case_latest` is frozen as of 2026-01-20 and will never update.
- Any ticket created against DEV/CERT NCR will **never** show up in DEV's `service_case` view, since there's no DEV AppFlow feeding it and the EventBridge rule that should trigger ingestion never fires.
- Build and test the close-sync Lambda logic against **PROD**'s `ncr_service_now_service_case_latest` instead — either via cross-account Athena read (preferred) or by seeding DEV DynamoDB with real PROD case numbers and querying PROD directly.
- If someone reports "the ticket-sync Lambda never reconciles anything in DEV," this is why — it's not a bug, DEV data just stopped moving.

---

## `meraki-client-info` — dead `notify_failure()` return (fixed)

File: `terraform/core_delta_lake/lambda/scripts/python/meraki-client-info/lambda_function.py`

`notify_failure()` had a stray `return` as its first line, before the docstring/SNS publish logic — meaning every call to it was a silent no-op and **all SNS failure alerts for this Lambda were disabled** without anyone getting an error. Confirmed fixed (the early `return` removed) as of 2026-09-21, and re-verified present as fixed again on 2026-09-27. If this Lambda's failures stop showing up in the SNS inbox again, check this function first — it's an easy line to accidentally reintroduce during a merge/copy-paste.

---

## General gotchas worth knowing

- **`git pull` can silently revert local edits** if the remote branch has an older copy of a file you'd changed but not yet committed/pushed — always re-read a file's actual current content after a pull before assuming your last edit is still there, especially for `lambda_function.py` files with recent behaviour changes.
- The main repo (`uk-snowfall-data-pipeline`) was on branch `dev`, remote `https://github.com/mcdonalds-corp-new/uk-snowfall-data-pipeline.git`, clean and pushed as of 2026-09-30.
- This `Localfiles` folder (handover docs, scripts, NCR/ServiceNow notes, incident-automation Terraform) was **not** part of any git repo during most of this work — it lived only on one engineer's machine. It's being pushed to its own backup repo for exactly that reason; if you're reading this from that backup repo, that migration already happened.

---

*Back to [the index](00-Handover-Index.md) for the full inventory, glossary and known gaps.*
