# Smartsheet Ingestion – Support Handover

**Dataset:** `smartsheet`
**Owner Lambda:** `uk-snowfall-dynamic-smartsheet-intergation-<env>`
**Schedule:** Daily 06:00 UTC (prod only; dev/nprod use no-op cron `0 0 31 2 ? *`)
**Region:** `eu-central-1`
**Repo:** `uk-snowfall-data-pipeline`

---

## 1. Purpose

Pulls one or more Smartsheet sheets via the Smartsheet REST API and lands them as JSON in S3. The landing-trigger Lambda then mirrors the JSON into `raw/`, which fires an EventBridge rule and starts the `uk-snowfall-smartsheet` Glue workflow for downstream ETL into Delta Lake (`preparation/` and `processed/`).

---

## 2. End-to-end flow

```
EventBridge schedule rule (prod 06:00 UTC)
  └─> Lambda: uk-snowfall-dynamic-smartsheet-intergation-<env>
        ├─ Reads Smartsheet API key from Secrets Manager (uk-snowfall / uk-snowfall-smartsheet-api-key)
        ├─ Calls Smartsheet REST API for each sheet ID in SHEET_IDS
        └─> Writes s3://eu-central1-<env>-uk-snowfall-landing-<account>/smartsheet/<sheet_name>.json
              └─> landing_trigger Lambda (mapping.json: "smartsheet" -> "smartsheet")
                    └─> Mirrors to s3://eu-central1-<env>-uk-snowfall-raw-<account>/smartsheet/<sheet_name>.json
                          └─> EventBridge rule: uk-snowfall-smartsheet-trigger-rule
                                └─> Glue workflow: uk-snowfall-smartsheet (EVENT trigger)
                                      └─> Preparation job  -> s3://...-preparation-<account>/smartsheet/
                                            └─> Processed job -> s3://...-processed-<account>/smartsheet/
```

---

## 3. Resource inventory

| # | Component | Resource / File | Notes |
|---|---|---|---|
| 1 | Smartsheet exporter Lambda code | `core_delta_lake/lambda/scripts/python/dynamic-smartsheet-intergation/lambda_function.py` | Python 3.12, stdlib `urllib` |
| 2 | Lambda zip (archive) | `data.archive_file.uk_snowfall_dynamic_smartsheet_intergation` in `core_delta_lake/lambda/main.tf` | Output: `scripts/zips/dynamic-smartsheet-intergation.zip` |
| 3 | Lambda function | `aws_lambda_function.uk_snowfall_dynamic_smartsheet_intergation` | `uk-snowfall-dynamic-smartsheet-intergation-<env>`, 512MB, 300s timeout |
| 4 | Lambda env vars | Same resource, `environment.variables` | `TARGET_BUCKET`, `SNS_TOPIC_ARN` |
| 5 | Schedule rule | `aws_cloudwatch_event_rule.uk_snowfall_dynamic_smartsheet_intergation_schedule` | `schedule_expression = var.smartsheet_6am_schedule` |
| 6 | Schedule target | `aws_cloudwatch_event_target.uk_snowfall_dynamic_smartsheet_intergation_target` | |
| 7 | Lambda permission | `aws_lambda_permission.uk_snowfall_dynamic_smartsheet_intergation_allow_eventbridge` | Allows `events.amazonaws.com` to invoke |
| 8 | Variable (lambda module) | `core_delta_lake/lambda/variables.tf` | `variable "smartsheet_6am_schedule" {}` |
| 9 | Variable (core module) | `core_delta_lake/variables.tf` | `variable "smartsheet_6am_schedule" {}` |
| 10 | Module wiring | `core_delta_lake/main.tf` | `smartsheet_6am_schedule = var.smartsheet_6am_schedule` |
| 11 | dev.tfvars | `terraform/dev.tfvars` | `cron(0 0 31 2 ? *)` (no-op) |
| 12 | nprod.tfvars | `terraform/nprod.tfvars` | `cron(0 0 31 2 ? *)` (no-op) |
| 13 | prod.tfvars | `terraform/prod.tfvars` | `cron(0 6 * * ? *)` |
| 14 | S3 landing folder | `core_delta_lake/s3/main_bucket/main.tf` (landing block) | Key `smartsheet = "smartsheet/"` |
| 15 | S3 raw folder | Same file (raw block) | Key `smartsheet = "smartsheet/"` |
| 16 | S3 preparation folder | Same file (preparation block) | Key `smartsheet = "smartsheet/"` |
| 17 | S3 processed folder | Same file (processed block) | Key `smartsheet = "smartsheet/"` |
| 18 | Glue workflow definition | `glue_resources/workflows/glue_workflow/main.tf` | `"smartsheet"` entry in `local.workflows` map, `trigger_type = "EVENT"` |
| 19 | EventBridge rule (raw S3 → workflow) | `other_resources/eventbridge/main.tf` | `aws_cloudwatch_event_rule.smartsheet_event_rule` – prefix `smartsheet/` on raw bucket |
| 20 | EventBridge target | Same file | `aws_cloudwatch_event_target.smartsheet_event_target` → `local.workflow_trigger_arns["smartsheet"]` |
| 21 | Landing→raw mapping | `core_delta_lake/lambda/scripts/python/landing_trigger/mapping.json` | `{ "fileName": "smartsheet", "destinationPath": "smartsheet" }` |

---

## 4. Configuration

### Lambda environment variables
| Var | Value | Source |
|---|---|---|
| `TARGET_BUCKET` | `eu-central1-<env>-uk-snowfall-landing-<account>` | Terraform |
| `SNS_TOPIC_ARN` | Snowfall topic ARN | Terraform (`var.sns_topic_arn`) |

### Hardcoded inside `lambda_function.py`
- `SHEET_IDS` – list of Smartsheet sheet IDs to export. **Update this list and redeploy** when adding/removing sheets.
- `SECRET_NAME = "uk-snowfall"`
- Secret JSON key: `uk-snowfall-smartsheet-api-key`

### Secrets Manager
- Secret name: `uk-snowfall` (already exists, shared across UK Snowfall integrations)
- Required key: `uk-snowfall-smartsheet-api-key`
- **Action for support:** ensure this key is set in each environment's secret. Rotate by updating the JSON value; no Lambda restart needed.

### Schedules
| Env | Cron | Effect |
|---|---|---|
| dev | `cron(0 0 31 2 ? *)` | Never fires (29 Feb workaround) |
| nprod | `cron(0 0 31 2 ? *)` | Never fires |
| prod | `cron(0 6 * * ? *)` | Daily 06:00 UTC |

To enable manual runs in dev/nprod, invoke the Lambda directly from the AWS console with an empty `{}` payload.

---

## 5. Output locations

| Stage | Path | Format |
|---|---|---|
| Landing | `s3://eu-central1-<env>-uk-snowfall-landing-<account>/smartsheet/<sheet_name>.json` | Raw JSON from Smartsheet API |
| Raw | `s3://eu-central1-<env>-uk-snowfall-raw-<account>/smartsheet/<sheet_name>.json` | Mirror of landing (landing_trigger) |
| Preparation | `s3://eu-central1-<env>-uk-snowfall-preparation-<account>/smartsheet/` | Delta table (after prep Glue job) |
| Processed | `s3://eu-central1-<env>-uk-snowfall-processed-<account>/smartsheet/` | Delta table (after processed Glue job) |

`<sheet_name>` is the Smartsheet sheet name sanitised to lowercase + underscores.

---

## 6. Monitoring

- **CloudWatch Log Group:** `/aws/lambda/uk-snowfall-dynamic-smartsheet-intergation-<env>`
- **Alerts:** failures call `notify_failure()` which publishes to `SNS_TOPIC_ARN` (Snowfall standard topic)
- **Glue workflow runs:** Glue Console → Workflows → `uk-snowfall-smartsheet`
- **EventBridge invocations:** CloudWatch Metrics → `AWS/Events` → `Invocations` for rule `uk-snowfall-dynamic-smartsheet-intergation-schedule-<env>` and `uk-snowfall-smartsheet-trigger-rule`

---

## 7. Common operational tasks

### Add a new Smartsheet sheet
1. Edit `SHEET_IDS` list in [`lambda_function.py`](../../uk-snowfall-data-pipeline/terraform/core_delta_lake/lambda/scripts/python/dynamic-smartsheet-intergation/lambda_function.py)
2. Commit + run pipeline → `terraform apply` → Lambda is repackaged via `archive_file` + `source_code_hash`
3. Next scheduled run (or manual invoke) will export the new sheet

### Rotate Smartsheet API key
1. Generate new token in Smartsheet
2. Update the `uk-snowfall-smartsheet-api-key` value inside the `uk-snowfall` Secrets Manager secret
3. No redeploy required – Lambda fetches the secret on every invocation

### Change schedule
1. Edit the relevant tfvars file (`prod.tfvars` for production)
2. `terraform apply`

### Pause ingestion temporarily
1. Set `prod.tfvars` `smartsheet_6am_schedule = "cron(0 0 31 2 ? *)"` and apply, **or**
2. Disable the EventBridge rule in the AWS console (manual change — will be reverted on next `terraform apply`)

### Re-run a failed day
1. Invoke `uk-snowfall-dynamic-smartsheet-intergation-prod` from the AWS console with payload `{}`
2. landing_trigger will mirror to raw → EventBridge will start the Glue workflow automatically

### Backfill into raw without re-fetching
- Copy/overwrite the existing JSON in the landing bucket; landing_trigger Lambda will re-mirror and re-trigger downstream.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No object in landing bucket after 06:00 UTC | Schedule rule disabled or Lambda error | Check CloudWatch logs for Lambda; verify rule is `ENABLED` in EventBridge |
| `botocore.errorfactory.ResourceNotFoundException` for secret | Secret missing in current account | Create/import `uk-snowfall` secret with key `uk-snowfall-smartsheet-api-key` |
| `KeyError: 'uk-snowfall-smartsheet-api-key'` | Secret exists but key not set | Add the key to the secret JSON value |
| HTTP 401/403 from Smartsheet | API key revoked or wrong | Rotate token, update secret |
| HTTP 429 from Smartsheet | Rate limit | Reduce sheet count or stagger; Smartsheet API limit is 300 req/min per token |
| Landing JSON present but no raw mirror | landing_trigger mapping not picking it up | Confirm `smartsheet` entry exists in [`mapping.json`](../../uk-snowfall-data-pipeline/terraform/core_delta_lake/lambda/scripts/python/landing_trigger/mapping.json); check landing_trigger Lambda logs |
| Raw JSON present but Glue workflow doesn't start | EventBridge rule wrong prefix or workflow trigger ARN missing | Check `uk-snowfall-smartsheet-trigger-rule` and `local.workflow_trigger_arns["smartsheet"]` exists |
| Glue workflow starts but jobs fail | Preparation/processed scripts missing or DQ rule failure | Check Glue job run logs; preparation/processed scripts live under `snowfall_pipeline/pipeline/{preparation,processed}/` |
| `NameError: notify_failure` in Lambda | Lambda code drift | The function is defined as a stub at top of `lambda_function.py`; restore if removed |

---

## 9. IAM requirements

The Lambda execution role (`var.role_assumed_arn`) needs:
- `secretsmanager:GetSecretValue` on the `uk-snowfall` secret
- `s3:PutObject` on the landing bucket `smartsheet/*` prefix
- `sns:Publish` on the Snowfall SNS topic
- `logs:CreateLogStream`, `logs:PutLogEvents` on its log group

These are expected to be already granted via the shared Snowfall pipeline role; verify if a fresh account is being onboarded.

---

## 10. Contacts

- **Pipeline owner:** William
- **Smartsheet API key custodian:** William (sheet owner must invite the integration user)
- **Repo:** `uk-snowfall-data-pipeline`
- **Deploy pipeline:** Standard Snowfall Terraform pipeline (dev → nprod → prod)
