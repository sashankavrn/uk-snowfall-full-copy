# Send notifications to EventBridge for all events in the bucket
# Bucket must exist before attaching a notification, will also 
# target a datashare processed trigger lambda which must too exist before attaching.

locals {
  processed_bucket_arn = data.terraform_remote_state.processed_state.outputs.processed_bucket_bucket_arn
}

resource "aws_s3_bucket_notification" "enable_event_bridge_for_datashare" {
  bucket      = local.processed_bucket_arn
  eventbridge = true
}


###################################### Datashare Processed Lambda Trigger #################################################

# Create an EventBridge rule for S3 object creation in the processed bucket
resource "aws_cloudwatch_event_rule" "datashare_processed_lambda_trigger" {
  name          = "uk-snowfall-datashare-processed-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.processed_state.outputs.processed_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.processed_state.outputs.processed_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "amazon_connect/"
      }, {
        "prefix": "service_now/change_request/"
      }, {
        "prefix": "service_now/incident/intraday/"
      }, {
        "prefix": "service_now/incident/daily/"
      }, {
        "prefix": "service_now/location/"
      }, {
        "prefix": "service_now/problem_record/"
      }, {
        "prefix": "service_now/service_request/"
      }, {
        "prefix": "service_now/service_offering/"
      }, {
        "prefix": "service_now/sys_user_group/"
      }, {
        "prefix": "service_now/sys_user/"
      }, {
        "prefix": "ods/trading_hours/"
      }, {
        "prefix": "ods/location_hierarchy/"
      }, {
        "prefix": "ods/adj_trading_hours/"
      }, {
        "prefix": "meraki/"
      }, {
        "prefix": "newrelic_rmp_device/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

# Attach the EventBridge rule to the Datashare Processed Lambda function
resource "aws_cloudwatch_event_target" "datashare_processed_lambda_trigger_target" {
  rule      = aws_cloudwatch_event_rule.datashare_processed_lambda_trigger.name
  arn       = aws_lambda_function.datashare_processed_trigger.arn  # Using your provided Lambda ARN
  role_arn  = var.role_assumed_arn
}
