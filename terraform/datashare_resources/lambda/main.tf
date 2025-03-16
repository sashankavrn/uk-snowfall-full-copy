# Archive the datashare_landing_trigger Python script
data "archive_file" "datashare_landing_trigger" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/datashare_landing_trigger/"
  output_path = "${path.module}/scripts/zips/datashare_landing_trigger.zip"
}

# Lambda function - datashare_landing_trigger
resource "aws_lambda_function" "datashare_landing_trigger" {
  filename         = "${path.module}/scripts/zips/datashare_landing_trigger.zip"
  function_name    = "uk-snowfall-datashare-landing-trigger-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime         = "python3.12"
  memory_size      = 512
  timeout          = 120
  description      = "Trigger to process data move NCR data to  landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/datashare_landing_trigger.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"
  ]
  environment {
    variables = {
      TARGET_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      DATASHARE_LANDING_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-datashare-landing-${var.account_number}"
      # SNS_TOPIC_ARN              = var.sns_topic_arn
    }
  }
}

# Adding permissions for datashare_landing_trigger Lambda
resource "aws_lambda_permission" "allow_landing_trigger" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.datashare_landing_trigger.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.datashare_landing_bucket_arn
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

# Adding permissions for datashare_processed_trigger Lambda
resource "aws_lambda_permission" "allow_processed_trigger" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.datashare_processed_trigger.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.datashare_processed_bucket_arn
}



########################################################################################################################
################################data push lambda to ncr webhook #######################################################
########################################################################################################################

# Archive the datashare_ncr_webhook Python script
data "archive_file" "datashare_ncr_webhook" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/datashare_ncr_webhook/"
  output_path = "${path.module}/scripts/zips/datashare_ncr_webhook.zip"
}

# Lambda function - datashare_ncr_webhook
resource "aws_lambda_function" "datashare_ncr_webhook" {
  filename         = "${path.module}/scripts/zips/datashare_ncr_webhook.zip"
  function_name    = "uk-snowfall-datashare-ncr-webhook-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Push data to  webhook for NCR data processing"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/datashare_ncr_webhook.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"
  ]
  environment {
    variables = {
      SOURCE_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      NCR_API_ENDPOINT  = "ncr-api.com"
      # SNS_TOPIC_ARN              = var.sns_topic_arn
    }
  }
}

resource "aws_lambda_permission" "allow_ncr_webhook" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.datashare_ncr_webhook.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.datashare_processed_bucket_arn
}

# # Adding permissions for datashare_ncr_webhook Lambda
# resource "aws_lambda_permission" "allow_ncr_webhook" {
#   statement_id  = "AllowExecutionFromAPIGateway"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.datashare_ncr_webhook.arn
#   principal     = "apigateway.amazonaws.com"
#   source_arn    = "*"
# }



# # CloudWatch Event Rule for Scheduled Trigger of datashare_processed_trigger
# resource "aws_cloudwatch_event_rule" "datashare_processed_schedule" {
#   name                = "datashare-processed-schedule"
#   description         = "Triggers the processed trigger Lambda function daily"
#   schedule_expression = "cron(0 3 * * ? *)"  # Runs at 3 AM UTC every day
# }

# # CloudWatch Event Target for datashare_processed_trigger
# resource "aws_cloudwatch_event_target" "invoke_datashare_processed_trigger" {
#   rule      = aws_cloudwatch_event_rule.datashare_processed_schedule.name
#   target_id = "datashare-processed-trigger-target"
#   arn       = aws_lambda_function.datashare_processed_trigger.arn
# }

# # Permission for EventBridge to invoke datashare_processed_trigger Lambda
# resource "aws_lambda_permission" "allow_eventbridge_invoke_processed_trigger" {
#   statement_id  = "AllowExecutionFromEventBridge"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.datashare_processed_trigger.function_name
#   principal     = "events.amazonaws.com"
#   source_arn    = aws_cloudwatch_event_rule.datashare_processed_schedule.arn
# }
