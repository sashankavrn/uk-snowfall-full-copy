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