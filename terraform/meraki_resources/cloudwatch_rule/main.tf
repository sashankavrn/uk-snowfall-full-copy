resource "aws_cloudwatch_event_rule" "hourly_lambda_trigger" {
  name                = "uk-snowfall-hourly-lambda-trigger-${var.environment}"
  description         = "Triggers Lambda function every hour"
  schedule_expression = "rate(1 hour)"  # Runs every hour
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.hourly_lambda_trigger.name
  target_id = "lambda"
  arn       = var.lambda_function_arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly_lambda_trigger.arn
}


resource "aws_cloudwatch_event_rule" "meraki_event_rule" {
  name        = "uk-snowfall-meraki-trigger-rule"
  description = "Object create events on bucket s3://landing bucket/meraki"

  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["eu-central1-dev-uk-snowfall-landing-295446674139"]
    },
    "object": {
      "key": [{
        "prefix": "meraki/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "processing_lambda_target" {
  rule      = aws_cloudwatch_event_rule.meraki_event_rule.name
  target_id = "processing_lambda"
  arn       = var.processing_lambda_arn
}

resource "aws_lambda_permission" "allow_eventbridge_processing_lambda" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_processing_trigger.lambda_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.meraki_event_rule.arn
}

