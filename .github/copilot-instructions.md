# Project Guidelines

## Code Style
- Keep Terraform changes scoped to the module being worked on: `core_delta_lake`, `glue_resources`, `other_resources`, or `datashare_resources`.
- Preserve existing naming patterns and variable structure in `.tf` files (`main.tf`, `variables.tf`, `output.tf`).
- For Lambda and utility Python under `terraform/**/scripts/python/**`, follow the existing direct style (simple functions, explicit logging, minimal abstraction).
- Avoid editing vendored JWT library sources unless explicitly requested (`terraform/core_delta_lake/websocketapi/jwt` and `terraform/core_delta_lake/lambda_layers/jwt_layer/python/jwt`).

## Architecture
- The platform is split across four Terraform top-level modules:
  - `terraform/core_delta_lake`: core ingest/runtime resources (S3, Lambda, API/websocket, AppFlow).
  - `terraform/glue_resources`: Glue scripts, workflows, and transformation pipeline resources.
  - `terraform/other_resources`: supporting resources and event integrations.
  - `terraform/datashare_resources`: data sharing distribution resources.
- Deployment and planning workflows use module-isolated remote state keys:
  - `snowfall-data-pipeline/<module>/terraform.tfstate`
- Cross-module dependencies are resolved through Terraform remote state (for example, `glue_resources` depends on outputs from `core_delta_lake`).

## Build and Test
- Use Terraform `1.7.4` to match CI workflows.
- Typical local Terraform loop for a module:
  - `cd terraform/<module>`
  - `terraform init -backend-config="bucket=<terraform_bucket_name>" -backend-config="key=snowfall-data-pipeline/<module>/terraform.tfstate" -backend-config="region=eu-central-1"`
  - `terraform plan -var-file=../dev.tfvars -out=tfplan`
  - `terraform apply tfplan`
- When changing infrastructure, run `terraform fmt -recursive` and `terraform validate` in the touched module(s).
- Environment var files are `terraform/dev.tfvars`, `terraform/nprod.tfvars`, and `terraform/prod.tfvars`.
- For proactive alerts lifecycle validation, use:
  - `terraform/core_delta_lake/lambda/scripts/python/snowfall-proactive-alerts/test_e2e_servicenow_lifecycle.py`
  - This is an integration test against real AWS resources, not a pure unit test.

## Conventions
- Keep changes aligned with CI behavior in `.github/workflows/snowfall_deploy.yml`:
  - `dev` branch maps to `dev.tfvars`
  - `main` branch maps to `nprod.tfvars`
  - `v2.*` tags map to `prod.tfvars`
- Prefer changed-module scope for Terraform work; do not plan/apply unrelated top-level modules.
- Do not hardcode secrets or credentials; use existing AWS secrets and environment variable patterns.
- Preserve timezone-aware behavior for UK operational logic (`Europe/London`) in proactive alert flows.
- In proactive alert records, preserve the mixed-record design in DynamoDB where `record_type` differentiates entities (for example `EMAIL_ALERT` and `SERVICENOW_CASE`).

## References
- Repo overview: `README.md`
- Deployment workflows:
  - `.github/workflows/snowfall_deploy.yml`
  - `.github/workflows/manual_plan.yml`
  - `.github/workflows/core_infra_deploy.yml`
  - `.github/workflows/glue_deploy.yml`
  - `.github/workflows/datashare_deploy.yml`
- Proactive alerts implementation:
  - `terraform/core_delta_lake/lambda/scripts/python/snowfall-proactive-alerts/lambda_function.py`
  - `terraform/core_delta_lake/lambda/scripts/python/snowfall-proactive-alerts/test_e2e_servicenow_lifecycle.py`
- Additional workspace documentation:
  - `../Localfiles/snowfall-docs/snowfall-proactive-lambdas-reference.md`
  - `../Localfiles/snowfall-docs/proactive alerts documentation.md`
  - `../Localfiles/snowfall-docs/ncr-voyix-integration-summary.md`