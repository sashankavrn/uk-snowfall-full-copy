# Snowfall Proactive Alerts → NCR ServiceNow Ticket Lifecycle

> **Status:** Active · **Environment:** DEV / NPROD / PROD · **Region:** eu-central-1
> **Owners:** UK Snowfall Data Pipeline team · **Last updated:** 2026-06-16

---

## 1. Overview

When a monitoring rule trips, the platform automatically:

1. **Creates** an NCR ServiceNow ticket.
2. **Attempts a self-heal** by running a proactive script on the affected device.
3. **Auto-closes** the ticket if the script fixed the problem, **or** leaves it open for a
   **field engineer**.
4. **Reconciles** an engineer's manual close in NCR back into our DynamoDB tables so the
   originating rule can raise future tickets again.

The goal is to reduce manual ticketing toil while keeping a fully auditable lifecycle and
never auto-closing a ticket a human is still working on.

---

## 2. Components

### Lambda functions

| Lambda | Responsibility |
| --- | --- |
| `snowfall-proactive-alerts` (**orchestrator**) | Evaluates rules via Athena, runs proactive scripts, sends email alerts, decides when to create/close ServiceNow cases. |
| `servicenow-proactive-ticket-creation` | **Opens** the NCR ticket (synchronous `CreateServiceRequest`), returns `ncr_ticket_id`. |
| `servicenow-proactive-ticket-close` | **Auto-closes** the ticket when a proactive script resolved the issue. |
| `servicenow-proactive-ticket-sync` | **Engineer-only reconciliation** (scheduled) — detects tickets a human closed in NCR and mirrors that state into DynamoDB. |
| `servicenow-tickets-cleanup` | Housekeeping / archival of old ticket records. |

### DynamoDB tables

| Table | Contents |
| --- | --- |
| `uk-snowfall-<env>-proactive-alerts` | Case rows (`record_type = SERVICENOW_CASE`) and email alert rows. Keyed by `alert_id`. |
| `uk-snowfall-<env>-service-now-tickets` | NCR ticket rows. Keyed by `ticket_id`. |

### Integration

- **NCR Voyix ServiceNow** — REST JSON over HTTPS, HTTP Basic Auth.
- **Athena view** `uk_snowfall_semantic.ncr_service_now_service_case_latest` — source of NCR
  ticket state used for engineer-close reconciliation.

---

## 3. End-to-end flow

```
[1] Rule trips (Athena query)
        |
        v
[2] Orchestrator (snowfall-proactive-alerts)
        |
        v
[3] Creation Lambda -> NCR CreateServiceRequest
        |
        v
[4] ncr_ticket_id written to case row + tickets table
        |
        v
[5] Run proactive script on device
        |
        v
[6] Did the script fix the issue?
        |
        +--- YES ---> [7a] Wait 15s -> Close Lambda -> NCR Resolve
        |                    |
        |                    v
        |             [8a] Ticket + case row marked CLOSED automatically
        |
        +--- NO ----> [7b] Ticket left OPEN for engineer dispatch
                             |
                             +--> [8b] Field engineer fixes and closes in NCR
                             |          |
                             |          v
                             |   [9b] Sync Lambda (scheduled) reads NCR Athena view
                             |          |
                             |          v
                             |   [10b] Ticket row + case row marked CLOSED
                             |         (closed_by = NCR_ENGINEER)
                             |
                             +--> [8c] Later alerts run: rule shows NO violation
                                        |
                                        v
                                 [9c] Orchestrator auto-closes the open ticket
                                       via Close Lambda ("issue cleared" note)
                                        |
                                        v
                                 [10c] Ticket row + case row marked CLOSED
```

### Flow A — Auto-resolved (happy path)

1. Rule trips → orchestrator opens a ticket (synchronously) and stores `ncr_ticket_id` on
   both the case row and the tickets table.
2. The proactive script runs on the device and **succeeds**.
3. After a **15-second delay** (to avoid a create/close race), the close Lambda resolves the
   ticket in NCR with the script result summary in the resolution notes.
4. The ticket row and case row are marked `CLOSED`.

> **✅ Validated end-to-end (2026-06-15, DEV).** Tested with rule `7`, restaurant `04071`,
> device `UK04071GSC01`, script `test_2.ps1`. Single orchestrator run completed the full
> lifecycle: rule evaluated → script triggered → `COMPLETED SUCCESSFULLY` → email `SENT` →
> NCR ticket created (`CS2086686`, `Status=SUCCESS`) → 15s wait → close Lambda invoked
> async (`202`) → NCR close `HTTP 200`, `Status=SUCCESS`. DynamoDB end state confirmed:
> ticket row `NCR#CS2086686` → `resolved_at` set, `ncr_close_status=SUCCESS`; case row
> → `status=CLOSED`. The close payload carried the device id and script output
> (`COMPLETED SUCCESSFULLY`) into NCR `ResolutionNotes` and `Remark`.
>
> **Design note:** Flow A logic lives only in the new-case branch of `process_rule`. If an
> OPEN case already exists for the rule, the duplicate guard skips create+close for that
> run — a successful script on a *later* run does **not** close an already-open ticket;
> that is handled by Flow C (`close_resolved_case_if_open`, which fires only when the
> rule's query returns no rows for that restaurant).

### Flow B — Engineer-only (manual resolution)

1. Rule trips → ticket opens, but the script **cannot fix** the issue (or no script applies).
2. The ticket is left **OPEN** for a field engineer.
3. The engineer resolves and closes the ticket directly in **NCR ServiceNow**.
4. The scheduled **sync Lambda** queries the NCR Athena view, detects the `Closed` / `Resolved`
   state, and marks **both** the ticket row **and** the originating case row as `CLOSED`
   (`closed_by = NCR_ENGINEER`).

### Flow C — Issue self-cleared on a later run

1. Rule trips on run 1 → ticket opens, but is left **OPEN** (script did not fix it, or no
   script applies). The case is tagged with the affected `restaurant_number`.
2. On a **later alerts run**, the orchestrator reconciles the open case against the rule's
   **current** violating restaurants:
   * **Restaurant-scoped case** → closed only when **that** restaurant is no longer in the
     violating set. Other restaurants still violating the same rule does **not** keep this
     ticket open, and does **not** trigger its close.
   * **Non-restaurant rule** → closed only when there are **no** violations at all.
3. When the close condition is met, the orchestrator invokes the close Lambda with a note,
   e.g.: *"A subsequent Snowfall proactive alert run found no violation for restaurant 0059 —
   the previously reported issue has been fixed. Closing this ticket automatically."*
4. The ticket row and case row are marked `CLOSED`.

> **✅ Validated end-to-end (2026-06-16, DEV).** Tested with rule `7`, restaurant `04071`.
> Run 1: query returned a violation → ticket `CS2086695` created, case `OPEN`. Run 2: query
> changed to return no rows (`... WHERE 1=0`) → orchestrator logged *"Rule 7 no longer
> violating for case CASE#… (restaurant=04071); auto-closing ticket (issue cleared on a
> later run)"* → close Lambda invoked async (`202`). Close Lambda took the `resolution_note`
> branch (no script results) and sent NCR `UpdateServiceRequest` → `HTTP 200`,
> `Status=SUCCESS`. DynamoDB end state confirmed: ticket row `NCR#CS2086695` → `resolved_at`
> set, `ncr_close_status=SUCCESS`, `close_notes` written; case row → `status=CLOSED`.
>
> **Where the close notes live:** the resolution text is sent to NCR (`ResolutionNotes` +
> `Remark`) **and** persisted to the **ticket row** (`close_notes`). The **case row** does
> **not** store the notes text — only `status=CLOSED`, `ncr_close_status`, `last_updated_at`.
>
> **Not supported:** “fail on run 1, succeed on run 2 → close.” While an OPEN case exists the
> duplicate guard skips create+close for that run (logs *“Open ServiceNow case … already
> exists; skipping duplicate ticket creation”*). Only Flow A (same run) or Flow C (query
> returns no rows for that restaurant) close a ticket.

| Open case restaurant | This run's violations | Action |
| --- | --- | --- |
| 0059 | 0059 still violating | **Keep open** — same restaurant still has the issue |
| 0059 | only 0114 violating | **Close 0059's ticket**; a new ticket is raised for 0114 |
| 0059 | none | **Close 0059's ticket** |

> **Note:** Flows B and C can race for the same ticket (engineer close vs. issue clearing).
> Both paths are idempotent — whichever fires first closes the ticket, and the other no-ops.

---

## 4. Recent change: engineer-only case-row reconciliation

### Problem

Previously, when an engineer closed a ticket in NCR, only the **ticket row** was reconciled.
The **case row** in `proactive-alerts` stayed `OPEN` indefinitely. Because the orchestrator
skips creating a new ticket while an open case exists for a rule, that rule could **never raise
another ticket** after a single engineer-handled incident.

### Fix

The `servicenow-proactive-ticket-sync` Lambda now also closes the originating case row when it
reconciles an engineer-closed ticket.

| Change | Detail |
| --- | --- |
| Terraform | Added `PROACTIVE_ALERTS_TABLE` environment variable to the sync Lambda. IAM unchanged (shared assumed role already has access to both tables). |
| Code | New `_load_open_case_rows()` builds an `ncr_ticket_id → alert_id` map of OPEN/CLOSING case rows. |
| Code | New `_close_case_row()` flips the case row to `CLOSED`, setting `ncr_state`, `close_notes`, `closed_by = NCR_ENGINEER`, `last_updated_at`. |
| Safety | `_close_case_row()` uses a DynamoDB `ConditionExpression` so it only closes still-open rows (idempotent, no clobbering). |

**Result:** once an engineer's close is reconciled, the rule is unblocked and can raise future
tickets again.

---

## 4a. Recent change: auto-close when the issue clears on a later run

### Problem

If a ticket was left **OPEN** (the proactive script did not fix it, or no script applied) and
the underlying issue later **cleared on its own**, the orchestrator simply skipped the rule on
subsequent runs (no violation = nothing to do). The ticket/case would stay `OPEN` until an
engineer closed it in NCR — even though the problem was already gone.

### Fix

The orchestrator now reconciles the open ticket against the rule's **current** violating
restaurants on **every** run, and closes it as soon as the ticket's own restaurant has cleared.

| Change | Detail |
| --- | --- |
| Orchestrator | Every run computes `violating_restaurants = get_unique_restaurants(records)` and calls `close_resolved_case_if_open(rule, violating_restaurants)` — even when there are no records. |
| Orchestrator | `close_resolved_case_if_open()` closes a **restaurant-scoped** case only when its `restaurant_number` is **not** in the current violating set; a **non-restaurant** rule closes only when there are no violations. |
| Orchestrator | `close_servicenow_ticket_if_open()` and `_invoke_servicenow_close()` now accept and forward an optional `resolution_note`. |
| Close Lambda | `lambda_handler` reads `event.get("resolution_note")`; `_build_update_payload()` uses it to build the NCR `ResolutionNotes` and `Remark`, and persists it to `close_notes`. |

**Restaurant scoping:** a ticket is **never** closed because a *different* restaurant cleared,
and it is **never** kept open just because *another* restaurant is still violating the same
rule. Each restaurant's ticket is reconciled independently.

**Resolution note text used (restaurant-scoped example):**

> A subsequent Snowfall proactive alert run found no violation for restaurant 0059 — the
> previously reported issue has been fixed. Closing this ticket automatically.

**Interaction with engineer flow:** this path and the hourly sync Lambda can both target the
same ticket. Both are idempotent, so whichever runs first closes the ticket and the other
no-ops. No duplicate closes or conflicts.

---

## 5. Schedule & configuration

| Setting | Value |
| --- | --- |
| Sync schedule | `cron(45 6-20 ? * MON-FRI *)` — weekdays, :45 past each hour, business hours (GMT) |
| Auto-close delay | `15 seconds` (hardcoded constant in the orchestrator) |
| NCR closed states detected | `Closed`, `Resolved` |
| Sync batch size | `100` case numbers per Athena query |
| Sync safety cap | `500` tickets per run |

---

## 6. Demo runbook

| # | Step | What to show |
| --- | --- | --- |
| 1 | Trigger / seed a rule trip | Orchestrator CloudWatch logs |
| 2 | Ticket opens | `service-now-tickets` row + case row both carry `ncr_ticket_id` |
| 3 | **Auto-close path** — success script | Ticket auto-resolves; resolution notes visible in NCR |
| 4 | **Engineer path** — failed/no script | Ticket left OPEN; close it manually in NCR |
| 5 | Trigger / wait for sync Lambda | Logs: `closed=… cases_closed=…` |
| 6 | Verify in DynamoDB | Ticket row has `closed_at`; case row `status=CLOSED`, `closed_by=NCR_ENGINEER` |
| 7 | Re-trip the same rule | A **new** ticket is raised (previously blocked) |
| 8 | **Issue-cleared path** — leave a ticket OPEN, then make the rule return no violation | Next alerts run auto-closes the ticket with the "issue cleared" note |

---

## 7. Talking points & FAQ

- **Does automation ever close a human's ticket?** No. The sync Lambda only *mirrors* the
  engineer's close from NCR — it never resolves a ticket on a human's behalf.
- **Is reconciliation safe to re-run?** Yes. `_close_case_row()` is idempotent via a
  conditional update; already-closed rows are skipped.
- **Why the 15-second delay?** It prevents the auto-close path from running before the
  `ncr_ticket_id` has been persisted from the synchronous create call.
- **DEV caveat:** the upstream `service_case` ingest is **stopped in DEV**, so engineer-close
  reconciliation only fully works against **PROD** live data (or historical DEV rows). Demo the
  engineer path in PROD or with seeded data.
- **What if the issue clears before an engineer acts?** The orchestrator auto-closes the open
  ticket on the next run where the ticket's restaurant is no longer violating, with an "issue
  cleared" resolution note. This applies to any open ticket, including engineer-dispatch ones.
- **What if another restaurant is still violating the same rule?** It has no effect on this
  ticket. Auto-close is restaurant-scoped: each restaurant's ticket is opened and closed based
  only on its own violation state.

---

## 8. Key DynamoDB attributes

### Case row (`proactive-alerts`, `record_type = SERVICENOW_CASE`)

| Attribute | Meaning |
| --- | --- |
| `alert_id` | Case row hash key (`CASE#<uuid>`) |
| `rule_id` | Rule that raised the case |
| `ncr_ticket_id` | NCR ticket reference (written at creation) |
| `status` | `OPEN` → `CLOSING` → `CLOSED` |
| `closed_by` | `NCR_ENGINEER` for engineer-reconciled closes |
| `ncr_state` | NCR state at close (`Closed` / `Resolved`) |

### Ticket row (`service-now-tickets`)

| Attribute | Meaning |
| --- | --- |
| `ticket_id` | Ticket row hash key (`NCR#<id>`) |
| `ncr_ticket_id` | NCR ticket reference |
| `status` | `SUCCESS` when created |
| `closed_at` | Set when reconciled/closed |
| `ncr_state`, `close_notes`, `resolution_code`, `resolved_at` | NCR close metadata |
