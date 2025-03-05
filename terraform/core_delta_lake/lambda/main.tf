# Zipping the lambda files

data "archive_file" "landing_trigger_script" {
  type        = "zip"
  source_dir = "${path.module}/scripts/python/landing_trigger/"
  output_path = "${path.module}/scripts/zips/landing-trigger.zip"
}


resource "aws_lambda_function" "uk_snowfall_landing_function" {
    filename = "${path.module}/scripts/zips/landing-trigger.zip"
    function_name = "uk-snowfall-landing-trigger-${var.environment}"
    role = var.role_assumed_arn
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    memory_size = 500
    timeout = 70
    description = "Move files from snowfall landing bucket into the raw bucket"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/landing-trigger.zip")
    tags = var.resource_tags
     layers = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
        SNS_TOPIC_ARN = var.sns_topic_arn
      }
    }
}

## Adding permissions for lambda
resource "aws_lambda_permission" "allow_landing_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_landing_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on = [ var.landing_bucket_arn,aws_lambda_function.uk_snowfall_landing_function ]
}

data "archive_file" "athena_views_script" {
  type        = "zip"
  source_dir = "${path.module}/scripts/python/create_athena_views/"
  output_path = "${path.module}/scripts/zips/create-athena-views.zip"
}

resource "aws_lambda_function" "uk_snowfall_create_athena_views" {
  filename = "${path.module}/scripts/zips/create-athena-views.zip"
  function_name = "uk-snowfall-create-athena-views-${var.environment}"
  role = var.role_assumed_arn
  handler = "lambda_function.lambda_handler"
  runtime = "python3.12"
  memory_size = 500
  timeout = 70
  description = "Create athena views in snowfall database,"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/create-athena-views.zip")
  tags = var.resource_tags
  layers = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
  environment {
    variables = {
      ATHENA_OUTPUT_LOCATION = "eu-central1-${var.environment}-uk-snowfall-athena-${var.account_number}"
      ATHENA_DATABASE = "uk_snowfall_semantic"
    }
  }
}


# ###########################################MERIKA FETCH LAMBDA#############################################


data "archive_file" "meraki-fetch-data" {
  type        = "zip"
  source_dir = "${path.module}/scripts/python/meraki-fetch-data/"
  output_path = "${path.module}/scripts/zips/meraki-fetch-data.zip"
}

resource "aws_lambda_function" "uk_snowfall_meraki_function" {
    filename = "${path.module}/scripts/zips/meraki-fetch-data.zip"
    function_name = "uk-snowfall-meraki-fetch-data-${var.environment}"
    role = var.role_assumed_arn
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    memory_size = 500
    timeout = 120
    description = "fetch data from meraki api and update to landing bucket"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/meraki-fetch-data.zip")
    tags = var.resource_tags
    layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1", # AWS SDK for Pandas
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"   # 
  ]
    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
        SNS_TOPIC_ARN = var.sns_topic_arn
      }
    }
}

## Adding permissions for lambda fetch data 
resource "aws_lambda_permission" "allow_landing_meraki_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_meraki_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on = [ var.landing_bucket_arn,aws_lambda_function.uk_snowfall_meraki_function ]
}


## C EventBridge Rule to trigger Lambda 
resource "aws_cloudwatch_event_rule" "meraki_lambda_schedule" {
  name                = "uk-snowfall-meraki-fetch-data-schedule"
  description         = "Triggers the Lambda function every minute"
  schedule_expression = "rate(1 hour)"  # Updated to 1 hour to testing  
  #  schedule_expression = "cron(0 1 * * ? *)"  # Runs at 1 AM UTC every day
}

## Add Lambda as the Target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_meraki_lambda" {
  rule      = aws_cloudwatch_event_rule.meraki_lambda_schedule.name
  target_id = "meraki-fetch-data-target"
  arn       = aws_lambda_function.uk_snowfall_meraki_function.arn
}

## Grant EventBridge Permission to Invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_meraki_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.meraki_lambda_schedule.arn
}
