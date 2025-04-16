# Archive the datashare_landing_trigger Python script
data "archive_file" "datashare_landing_trigger" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/datashare_landing_trigger/"
  output_path = "${path.module}/scripts/zips/datashare_landing_trigger.zip"
}

# Lambda function - datashare_landing_trigger
resource "aws_lambda_function" "datashare_landing_trigger" {
  filename                   = "${path.module}/scripts/zips/datashare_landing_trigger.zip"
  function_name              = "uk-snowfall-datashare-landing-trigger-${var.environment}"
  role                       = var.role_assumed_arn
  handler                    = "lambda_function.lambda_handler"
  runtime                    = "python3.12"
  memory_size                = 1024
  timeout                    = 300  # Increased from 120 to 300 seconds (5 minutes)
  description                = "Trigger to process data move NCR data to landing bucket"
  source_code_hash           = filebase64sha256("${path.module}/scripts/zips/datashare_landing_trigger.zip")
  tags                       = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"
  ]
  environment {
    variables = {
      TARGET_BUCKET             = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      DATASHARE_LANDING_BUCKET  = "eu-central1-${var.environment}-uk-snowfall-datashare-landing-${var.account_number}"
      # SNS_TOPIC_ARN            = var.sns_topic_arn
    }
  }
  reserved_concurrent_executions = 10
}









########################################################################################################################
################################datashare-processed-trigger#############################################################
########################################################################################################################

# Archive the datashare_processed_trigger Python script
data "archive_file" "datashare_processed_trigger" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/datashare_processed_trigger/"
  output_path = "${path.module}/scripts/zips/datashare_processed_trigger.zip"
}

# Lambda function - datashare_processed_trigger
resource "aws_lambda_function" "datashare_processed_trigger" {
  filename         = "${path.module}/scripts/zips/datashare_processed_trigger.zip"
  function_name    = "uk-snowfall-datashare-processed-trigger-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 180
  description      = "Trigger to copy data from orginal processed bucket to datashare processed bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/datashare_processed_trigger.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"
  ]
  environment {
    variables = {
      TARGET_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      SOURCE_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-processed-${var.account_number}"
      # SNS_TOPIC_ARN              = var.sns_topic_arn
    }
  }
}

# # Adding permissions for datashare_processed_trigger Lambda
# resource "aws_lambda_permission" "allow_processed_trigger" {
#   statement_id  = "AllowExecutionFromS3Bucket"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.datashare_processed_trigger.arn
#   principal     = "s3.amazonaws.com"
#   source_arn    = var.datashare_processed_bucket_arn
# }

# --------------------------------------------------------
# CloudWatch Event configuration - trigger every 5 minutes-for testing 
# --------------------------------------------------------

# CloudWatch Event Rule to trigger datashare_processed_trigger Lambda every 5 minutes
resource "aws_cloudwatch_event_rule" "datashare_trigger_schedule" {
  name                = "uk-snowfall-datashare-processed-trigger-schedule"
  description         = "Triggers the datashare_processed_trigger Lambda every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

# Add datashare_processed_trigger Lambda as the target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_datashare_processed_trigger" {
  rule      = aws_cloudwatch_event_rule.datashare_trigger_schedule.name
  target_id = "datashare-processed-trigger-target"
  arn       = aws_lambda_function.datashare_processed_trigger.arn
}

# Grant EventBridge permission to invoke the datashare_processed_trigger Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_datashare" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.datashare_processed_trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.datashare_trigger_schedule.arn
}