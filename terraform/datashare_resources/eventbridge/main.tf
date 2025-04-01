# Fetch the core state from S3
data "terraform_remote_state" "core_infra_state" {
  backend = "s3"

  config = {
    bucket  = "eu-central1-dev-uk-snowfall-terraform-295446674139"  # Core state bucket
    key     = "snowfall-data-pipeline/core_delta_lake/terraform.tfstate"  # Path to your state file
    region  = "eu-central-1"
  }
}

# Define a local variable for the processed bucket name from the core state
locals {
  processed_bucket_name = data.terraform_remote_state.core_infra_state.outputs.processed_bucket_name
}

# Enable EventBridge notifications on the processed bucket
resource "aws_s3_bucket_notification" "enable_event_bridge_for_datashare" {
  bucket      = local.processed_bucket_name
  eventbridge = true
}

###################################### Datashare Processed Lambda Trigger #################################################

# Create an EventBridge rule for S3 object creation in the processed bucket
resource "aws_cloudwatch_event_rule" "datashare_processed_lambda_trigger" {
  name          = "uk-snowfall-datashare-processed-trigger-rule"
  description   = "Object create events on bucket s3://${local.processed_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${local.processed_bucket_name}"]
    },
    "object": {
      "key": [
        { "prefix": "amazon_connect/" },
        { "prefix": "service_now/change_request/" },
        { "prefix": "service_now/incident/intraday/" },
        { "prefix": "service_now/incident/daily/" },
        { "prefix": "service_now/location/" },
        { "prefix": "service_now/problem_record/" },
        { "prefix": "service_now/service_request/" },
        { "prefix": "service_now/service_offering/" },
        { "prefix": "service_now/sys_user_group/" },
        { "prefix": "service_now/sys_user/" },
        { "prefix": "ods/trading_hours/" },
        { "prefix": "ods/location_hierarchy/" },
        { "prefix": "ods/adj_trading_hours/" },
        { "prefix": "meraki/" },
        { "prefix": "newrelic/" }
      ]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

# Attach the EventBridge rule to the Datashare Processed Lambda function
resource "aws_cloudwatch_event_target" "datashare_processed_lambda_trigger_target" {
  rule     = aws_cloudwatch_event_rule.datashare_processed_lambda_trigger.name
  arn      = var.datashare_processed_trigger_lambda_arn
  role_arn = var.role_assumed_arn
}
