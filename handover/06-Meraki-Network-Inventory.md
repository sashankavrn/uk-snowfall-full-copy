# Group 5 — Meraki Network Inventory

Cisco Meraki manages the in-restaurant network hardware (access points, switches). Both Lambdas talk to the Meraki Dashboard REST API for a single hard-coded organisation ID and land inventory JSON in the landing bucket. Meraki's API is paginated via a `Link` response header rather than a simple offset, which both Lambdas implement their own retry/pagination logic for.

---

## meraki-client-info
**Trigger:** EventBridge, roughly every minute per the schedule config (self-recursive design, see below) · **Source:** `core_delta_lake/lambda/scripts/python/meraki-client-info/`

Fetches connected **client** (end-device, e.g. tills/kiosks/laptops joined to the network) info across all Meraki networks in the organisation. Because a full client scan across every restaurant network can run long, this Lambda is deliberately designed to re-invoke itself: it processes a bounded number of networks per run (`networkPerRun = 500`) and self-limits to `maxRuns = 50` invocations, checking `minimumRemainingTime` before deciding whether to continue in the same invocation or hand off. Intermediate state is staged in a temp S3 location (`TEMP_BUCKET`/`meraki/client_info/`) before the final combined output lands at `OUTPUT_BUCKET`/`meraki/client_info/`.

It derives `restaurant_number` from the Meraki device/network name via regex. **Update (2026-09-21): the dead `return` at the top of `notify_failure()` has been fixed** — SNS failure notifications for this Lambda now fire correctly again; previously they were silently disabled. Also note Terraform's schedule comment for the related `meraki-client-info` EventBridge rule says "STOPPED FOR NOW", so confirm current schedule state before assuming it's actively running.

## meraki-fetch-device
**Trigger:** EventBridge, roughly every minute (`var.meraki_schedule`) · **Source:** `.../meraki-fetch-device/`

Fetches the **device** inventory (access points, switches, etc. — the physical hardware itself, not connected clients) for the organisation via a single paginated call, extracts a restaurant number from each device name by regex, and writes the combined list as one timestamped JSON file to the landing bucket for the Glue pipeline. Unlike the client-info Lambda, this one is simple/single-pass — the device list is small enough not to need the self-recursion trick.

Its `notify_failure` implementation is "normal" (does publish to SNS if `SNS_TOPIC_ARN` is set), which is a useful contrast to `meraki-client-info` above when explaining to the team why one Meraki job alerts on failure and the other currently doesn't.

---

## Troubleshooting / Runbook

| Symptom | First things to check |
|---|---|
| meraki-client-info seems to have stopped running | Terraform's schedule comment says "STOPPED FOR NOW" for this rule — confirm the EventBridge rule is actually enabled before assuming a code failure |
| meraki-client-info run looks incomplete/partial | Check `maxRuns`/`networkPerRun` self-recursion limits and the `TEMP_BUCKET` staging area — a run can legitimately hand off to a subsequent invocation rather than finishing in one Lambda execution |
| Restaurant number missing/wrong on Meraki data | Both Lambdas derive `restaurant_number` via regex on the device/network name — a Meraki dashboard naming convention change breaks this silently |
| No SNS alert despite an obvious failure | `meraki-client-info`'s `notify_failure()` dead-`return` bug was fixed 2026-09-21 — if this recurs, check for a re-introduced early return or a missing `SNS_TOPIC_ARN` env var |

---
*[Back to the index](00-Handover-Index.md).*
