# Zipping the lambda files

data "archive_file" "landing_trigger_script" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/landing_trigger/"
  output_path = "${path.module}/scripts/zips/landing-trigger.zip"
}


resource "aws_lambda_function" "uk_snowfall_landing_function" {
  filename         = "${path.module}/scripts/zips/landing-trigger.zip"
  function_name    = "uk-snowfall-landing-trigger-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 500
  timeout          = 70
  description      = "Move files from snowfall landing bucket into the raw bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/landing-trigger.zip")
  tags             = var.resource_tags
  layers           = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
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
  depends_on    = [var.landing_bucket_arn, aws_lambda_function.uk_snowfall_landing_function]
}

#Lambda for creating athena views
data "archive_file" "athena_views_script" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/create_athena_views/"
  output_path = "${path.module}/scripts/zips/create-athena-views.zip"
}

resource "aws_lambda_function" "uk_snowfall_create_athena_views" {
  filename         = "${path.module}/scripts/zips/create-athena-views.zip"
  function_name    = "uk-snowfall-create-athena-views-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 500
  timeout          = 70
  description      = "Create athena views in snowfall database,"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/create-athena-views.zip")
  tags             = var.resource_tags
  layers           = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
  environment {
    variables = {
      ATHENA_OUTPUT_LOCATION = "eu-central1-${var.environment}-uk-snowfall-athena-${var.account_number}"
      ATHENA_DATABASE        = "uk_snowfall_semantic"
      S3_BUCKET_NAME         = "eu-central1-${var.environment}-uk-snowfall-artifact-${var.account_number}"
      WORKGROUP_NAME         = "uk-snowfall-pipeline"
    }
  }
}

## Adding permissions for lambda
resource "aws_lambda_permission" "allow_artifact_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_create_athena_views.arn
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.artifact_bucket.arn
  depends_on    = [var.artifact_bucket_arn, aws_lambda_function.uk_snowfall_create_athena_views]
}

data "aws_s3_bucket" "artifact_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-artifact-${var.account_number}"
}

resource "aws_s3_bucket_notification" "athena_views_trigger_notification" {
  bucket = data.aws_s3_bucket.artifact_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.uk_snowfall_create_athena_views.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "athena_views/"
    id                  = "Athena view creation"
  }

  depends_on = [
    data.aws_s3_bucket.artifact_bucket,
    aws_lambda_permission.allow_artifact_bucket,
    aws_lambda_function.uk_snowfall_create_athena_views
  ]
}

############################################MERAKI FETCH DEVICE INFO LAMBDA#############################################

data "archive_file" "meraki-fetch-device" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/meraki-fetch-device/"
  output_path = "${path.module}/scripts/zips/meraki-fetch-device.zip"
}

resource "aws_lambda_function" "uk_snowfall_meraki_function" {
  filename         = "${path.module}/scripts/zips/meraki-fetch-device.zip"
  function_name    = "uk-snowfall-meraki-fetch-device-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 500
  timeout          = 120
  description      = "fetch data from meraki api and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/meraki-fetch-device.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1", # AWS SDK for Pandas
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"
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
  depends_on    = [var.landing_bucket_arn, aws_lambda_function.uk_snowfall_meraki_function]
}

## EventBridge Rule to trigger Lambda 
resource "aws_cloudwatch_event_rule" "meraki_lambda_schedule" {
  name                = "uk-snowfall-meraki-fetch-device-schedule"
  description         = "Triggers the Lambda function every minute"
  schedule_expression = var.meraki_schedule
}

## Add Lambda as the Target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_meraki_lambda" {
  rule      = aws_cloudwatch_event_rule.meraki_lambda_schedule.name
  target_id = "meraki-fetch-device-target"
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



##########################################################################NEWRELIC-RMP-DEVICE-INFO-FETCH###################################################

# Archive the newrelic-device-info Python script
data "archive_file" "newrelic_fetch_data" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-rmp-fetch-device/"
  output_path = "${path.module}/scripts/zips/newrelic-rmp-fetch-device.zip"
}

# Lambda Function for fetching New Relic device info
resource "aws_lambda_function" "uk_snowfall_newrelic_function" {
  filename         = "${path.module}/scripts/zips/newrelic-rmp-fetch-device.zip"
  function_name    = "uk-snowfall-newrelic-rmp-fetch-device-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 2048
  timeout          = 720
  description      = "Fetch data from New Relic API and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-fetch-device.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1", # AWS SDK for Pandas
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"   # Requests library
  ]
  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

# Adding permissions for lambda fetch data 
resource "aws_lambda_permission" "allow_landing_newrelic_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on    = [var.landing_bucket_arn, aws_lambda_function.uk_snowfall_newrelic_function]
}

# CloudWatch Event Rule to trigger Lambda
resource "aws_cloudwatch_event_rule" "newrelic_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-fetch-device-schedule"
  description         = "Triggers the Lambda function every hour"
  schedule_expression = var.newrelic_1am_schedule #"cron(0 1 * * ? *)"  # Runs at 1:01,2:01.. AM UTC every day
}

# Add Lambda as the Target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_newrelic_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_lambda_schedule.name
  target_id = "newrelic-rmp-fetch-device-target"
  arn       = aws_lambda_function.uk_snowfall_newrelic_function.arn
}

# Grant EventBridge Permission to Invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_lambda_schedule.arn
}


########################################################################### NEWRELIC-RMP-DEVICE-METRICS##########################################################################

# Archive the newrelic-device-metrics Python script
data "archive_file" "newrelic_metrics_data" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-rmp-device-metrics/"
  output_path = "${path.module}/scripts/zips/newrelic-rmp-device-metrics.zip"
}

# Lambda Function for fetching New Relic device metrics
resource "aws_lambda_function" "uk_snowfall_newrelic_metrics_function" {
  filename         = "${path.module}/scripts/zips/newrelic-rmp-device-metrics.zip"
  function_name    = "uk-snowfall-newrelic-rmp-device-metrics-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 4096 # Increased 
  timeout          = 720
  description      = "Fetch metrics data from New Relic API and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-device-metrics.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1", # AWS SDK for Pandas
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"   # Requests library
  ]
  environment {
    variables = {
      DATASHARE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      TARGET_BUCKET    = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN    = var.sns_topic_arn

    }
  }
}



# CloudWatch Event Rule to trigger Lambda every 10 minutes
resource "aws_cloudwatch_event_rule" "newrelic_metrics_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-device-metrics-schedule"
  description         = "Triggers the New Relic device metrics Lambda every 10 minutes"
  schedule_expression = var.newrelic_10min_schedule #"rate(10 minutes)"
}

# Add Lambda as the target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_newrelic_metrics_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_metrics_lambda_schedule.name
  target_id = "newrelic-rmp-device-metrics-target"
  arn       = aws_lambda_function.uk_snowfall_newrelic_metrics_function.arn
}

# Grant EventBridge permission to invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_metrics" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_metrics_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_metrics_lambda_schedule.arn
}

###########################################################################
# NEWRELIC-RMP-PROCESS-INFO
###########################################################################

# Archive the newrelic-device-metrics Python script
data "archive_file" "newrelic_process_info_data" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-rmp-process-info/"
  output_path = "${path.module}/scripts/zips/newrelic-rmp-process-info.zip"
}

# Lambda Function for fetching New Relic process info
resource "aws_lambda_function" "uk_snowfall_newrelic_process_info_function" {
  filename         = "${path.module}/scripts/zips/newrelic-rmp-process-info.zip"
  function_name    = "uk-snowfall-newrelic-rmp-process-info-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 4096
  timeout          = 720
  description      = "Fetch process info from New Relic API and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-process-info.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:15"
  ]
  environment {
    variables = {
      DATASHARE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      TARGET_BUCKET    = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN    = var.sns_topic_arn
    }
  }
}

# CloudWatch Event Rule to trigger Lambda every 10 minutes
resource "aws_cloudwatch_event_rule" "newrelic_process_info_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-process-info-schedule"
  description         = "Triggers the New Relic process info Lambda every 10 minutes"
  schedule_expression = var.newrelic_10min_schedule #  "rate(10 minutes)"
}

# Add Lambda as the target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_newrelic_process_info_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_process_info_lambda_schedule.name
  target_id = "newrelic-rmp-process-info-target"
  arn       = aws_lambda_function.uk_snowfall_newrelic_process_info_function.arn
}

# Grant EventBridge permission to invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_process_info" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_process_info_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_process_info_lambda_schedule.arn
}

###########################################################################
# NEWRELIC-RMP-NETWORK-INFO
###########################################################################

###########################################################################
# Archive the newrelic-network-metrics Python script
###########################################################################
data "archive_file" "newrelic_network_info_data" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-rmp-network-info/"
  output_path = "${path.module}/scripts/zips/newrelic-rmp-network-info.zip"
}

###########################################################################
# Lambda Function for fetching New Relic network info
###########################################################################
resource "aws_lambda_function" "uk_snowfall_newrelic_network_info_function" {
  filename         = "${path.module}/scripts/zips/newrelic-rmp-network-info.zip"
  function_name    = "uk-snowfall-newrelic-rmp-network-info-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 4096
  timeout          = 720
  description      = "Fetch network info from New Relic API and write to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-network-info.zip")
  tags             = var.resource_tags

  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:15"
  ]

  environment {
    variables = {
      DATASHARE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      TARGET_BUCKET    = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN    = var.sns_topic_arn
    }
  }
}

###########################################################################
# CloudWatch EventBridge Rule to trigger Lambda every 10 minutes
###########################################################################
resource "aws_cloudwatch_event_rule" "newrelic_network_info_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-network-info-schedule"
  description         = "Triggers the New Relic network info Lambda every 10 minutes"
  schedule_expression = var.newrelic_10min_schedule #"rate(10 minutes)"
}

###########################################################################
# Target binding between the schedule and the Lambda
###########################################################################
resource "aws_cloudwatch_event_target" "invoke_newrelic_network_info_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_network_info_lambda_schedule.name
  target_id = "newrelic-rmp-network-info-target"
  arn       = aws_lambda_function.uk_snowfall_newrelic_network_info_function.arn
}

###########################################################################
# Grant EventBridge permission to invoke the Lambda
###########################################################################
resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_network_info" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_network_info_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_network_info_lambda_schedule.arn
}

###########################################################################
# NEWRELIC-RMP-NETWORK-INFO-DAILY-AGGREGATE
###########################################################################

###########################################################################
# Archive the newrelic-network-metrics Python script
###########################################################################
data "archive_file" "newrelic_network_info_daily_aggregate_data" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-rmp-network-info-daily-aggregate/"
  output_path = "${path.module}/scripts/zips/newrelic-rmp-network-info-daily-aggregate.zip"
}

###########################################################################
# Lambda Function for fetching New Relic network info
###########################################################################
resource "aws_lambda_function" "uk_snowfall_newrelic_network_info_daily_aggregate_function" {
  filename         = "${path.module}/scripts/zips/newrelic-rmp-network-info-daily-aggregate.zip"
  function_name    = "uk-snowfall-newrelic-rmp-network-info-daily-aggregate-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 4096
  timeout          = 720
  description      = "Fetch daily aggregated network info from New Relic API and write to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-network-info-daily-aggregate.zip")
  tags             = var.resource_tags

  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:15"
  ]

  environment {
    variables = {
      DATASHARE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      TARGET_BUCKET    = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN    = var.sns_topic_arn
    }
  }
}

###########################################################################
# CloudWatch EventBridge Rule to trigger Lambda at 1 AM UTC daily
###########################################################################
resource "aws_cloudwatch_event_rule" "newrelic_network_info_daily_aggregate_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-network-info-daily-aggregate-schedule"
  description         = "Triggers the New Relic daily aggregate network info Lambda at 1 AM UTC"
  schedule_expression = var.newrelic_1am_schedule #"cron(0 1 * * ? *)"
}

###########################################################################
# Target binding between the schedule and the Lambda
###########################################################################
resource "aws_cloudwatch_event_target" "invoke_newrelic_network_info_daily_aggregate_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_network_info_daily_aggregate_lambda_schedule.name
  target_id = "newrelic-rmp-network-info-daily-aggregate-target"
  arn       = aws_lambda_function.uk_snowfall_newrelic_network_info_daily_aggregate_function.arn
}

###########################################################################
# Grant EventBridge permission to invoke the Lambda
###########################################################################
resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_network_info_daily_aggregate" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_newrelic_network_info_daily_aggregate_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_network_info_daily_aggregate_lambda_schedule.arn
}




#######################################################################
# NEWRELIC-DIGITAL-GMA-FOE-RESPONSE LAMBDA
#######################################################################

# Archive the Python script for Lambda deployment
data "archive_file" "newrelic_digital_gma_foe_response" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-digital-gma-foe-response/"
  output_path = "${path.module}/scripts/zips/newrelic-digital-gma-foe-response.zip"
}


# Lambda Function for fetching New Relic Digital Response info
resource "aws_lambda_function" "newrelic_digital_gma_foe_response_function" {
  filename         = "${path.module}/scripts/zips/newrelic-digital-gma-foe-response.zip"
  function_name    = "uk-snowfall-newrelic-digital-gma-foe-response-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 2048
  timeout          = 720
  description      = "Fetch digital response data from New Relic API and upload to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-digital-gma-foe-response.zip")
  tags             = var.resource_tags

  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"
  ]

  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

resource "aws_lambda_permission" "allow_landing_newrelic_digital_gma_foe_response_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.newrelic_digital_gma_foe_response_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on = [
    aws_lambda_function.newrelic_digital_gma_foe_response_function
  ]
}

resource "aws_cloudwatch_event_rule" "newrelic_digital_gma_foe_response_lambda_schedule" {
  name                = "uk-snowfall-newrelic-digital-gma-foe-response-schedule"
  description         = "Triggers the Lambda function every hour at 5 minutes past the hour"
  schedule_expression = var.newrelic_5min_schedule #"cron(5 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "invoke_newrelic_digital_gma_foe_response_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_digital_gma_foe_response_lambda_schedule.name
  target_id = "newrelic-digital-gma-foe-response-target"
  arn       = aws_lambda_function.newrelic_digital_gma_foe_response_function.arn
}

resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_digital_gma_foe_response" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.newrelic_digital_gma_foe_response_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_digital_gma_foe_response_lambda_schedule.arn
}

#######################################################################
# NEWRELIC-DIGITAL-3PO-FOE-RESPONSE LAMBDA
#######################################################################
# Archive the Python script for Lambda deployment
data "archive_file" "newrelic_digital_3po_foe_response" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/newrelic-digital-3po-foe-response/"
  output_path = "${path.module}/scripts/zips/newrelic-digital-3po-foe-response.zip"
}

resource "aws_lambda_function" "newrelic_digital_3po_foe_response_function" {
  filename         = "${path.module}/scripts/zips/newrelic-digital-3po-foe-response.zip"
  function_name    = "uk-snowfall-newrelic-digital-3po-foe-response-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler" # Make sure this matches the Python file inside the ZIP
  runtime          = "python3.12"
  memory_size      = 2048
  timeout          = 720
  description      = "Fetch digital response data from New Relic API and upload to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-digital-3po-foe-response.zip")
  tags             = var.resource_tags

  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"
  ]

  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

resource "aws_lambda_permission" "allow_landing_newrelic_digital_3po_foe_response_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.newrelic_digital_3po_foe_response_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on    = [aws_lambda_function.newrelic_digital_3po_foe_response_function]
}

resource "aws_cloudwatch_event_rule" "newrelic_digital_3po_foe_response_lambda_schedule" {
  name                = "uk-snowfall-newrelic-digital-3po-foe-response-schedule"
  description         = "Triggers the Lambda function every hour at 5 minutes past the hour"
  schedule_expression = var.newrelic_5min_schedule #"cron(5 * * * ? *)"
}


resource "aws_cloudwatch_event_target" "invoke_newrelic_digital_3po_foe_response_lambda" {
  rule      = aws_cloudwatch_event_rule.newrelic_digital_3po_foe_response_lambda_schedule.name
  target_id = "newrelic-digital-3po-foe-response-target"
  arn       = aws_lambda_function.newrelic_digital_3po_foe_response_function.arn
}

resource "aws_lambda_permission" "allow_eventbridge_invoke_newrelic_digital_3po_foe_response" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.newrelic_digital_3po_foe_response_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.newrelic_digital_3po_foe_response_lambda_schedule.arn
}

############################################ SERVICE AGENT LAMBDAS  #############################################

data "archive_file" "service_agent_upload_s3_jwt_authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-upload-s3-jwt-authorizer/"
  output_path = "${path.module}/scripts/zips/service-agent-upload-s3-jwt-authorizer.zip"
}

resource "aws_lambda_function" "uk_snowfall_service_agent_authorizer_function" {
  filename         = "${path.module}/scripts/zips/service-agent-upload-s3-jwt-authorizer.zip"
  function_name    = "uk-snowfall-service-agent-upload-s3-jwt-authorizer-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 120
  description      = "Upload data to S3 using JWT authentication via API"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-upload-s3-jwt-authorizer.zip")
  tags             = var.resource_tags
  layers = [
    var.jwt_layer_arn
  ]



  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn

    }
  }
}

## Adding permissions for lambda upload data 
resource "aws_lambda_permission" "allow_service_agent_bucket_auth" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_service_agent_authorizer_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.service_agent_bucket_arn

}


############################################ SERVICE AGENT -UPLOAD S3 LAMBDA VIA API#############################################

data "archive_file" "service_agent_upload_s3" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-upload-s3/"
  output_path = "${path.module}/scripts/zips/service-agent-upload-s3.zip"
}

resource "aws_lambda_function" "uk_snowfall_service_agent_function" {
  filename         = "${path.module}/scripts/zips/service-agent-upload-s3.zip"
  function_name    = "uk-snowfall-service-agent-upload-s3-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 120
  description      = "Upload data to S3 using JWT authentication via api"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-upload-s3.zip")
  tags             = var.resource_tags
  layers           = []
  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

## Adding permissions for lambda upload data 
resource "aws_lambda_permission" "allow_service_agent_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_service_agent_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.service_agent_bucket_arn
  depends_on    = [aws_lambda_function.uk_snowfall_service_agent_function]
}


# ############################################ SERVICE AGENT SERVER FILES COPY TO RAW BUCKET  #############################################

# ## Archive the service-agent-server-files Python script
data "archive_file" "service_agent_server_files" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-server-files/"
  output_path = "${path.module}/scripts/zips/service-agent-server-files.zip"
}

## Lambda function - service-agent-server-files
resource "aws_lambda_function" "service_agent_server_files" {
  filename         = data.archive_file.service_agent_server_files.output_path
  function_name    = "uk-snowfall-service-agent-server-files-copy-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Triggered by S3 to copy files from uploads/ to service-agent-server-files/"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-server-files.zip")
  tags             = var.resource_tags

  environment {
    variables = {
      SOURCE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

## Adding permissions for lambda
resource "aws_lambda_permission" "allow_service_agent_s3_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.service_agent_server_files.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.service_agent_bucket_arn
  depends_on = [
    var.service_agent_bucket_arn,
    aws_lambda_function.service_agent_server_files
  ]
}


data "aws_s3_bucket" "service_agent_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
}

resource "aws_s3_bucket_notification" "service_agent_server_files_trigger" {
  bucket = data.aws_s3_bucket.service_agent_bucket.id


  lambda_function {
    lambda_function_arn = aws_lambda_function.service_agent_server_files.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
  }

  depends_on = [
    aws_lambda_permission.allow_service_agent_s3_bucket
  ]
}



############################################ SERVICE AGENT SERVER LIST EXTRACT  #############################################

# Archive the Lambda script for extracting service agent server info
data "archive_file" "service_agent_server_extract_script" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-server-list-extract/"
  output_path = "${path.module}/scripts/zips/service-agent-server-list-extract.zip"
}

# Lambda Function to extract service agent server info from Athena
resource "aws_lambda_function" "service_agent_server_extract_function" {
  filename         = "${path.module}/scripts/zips/service-agent-server-list-extract.zip"
  function_name    = "uk-snowfall-service-agent-server-list-extract-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Extracts service agent server list from Athena and stores it in S3 folder-server_list "
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-server-list-extract.zip")
  tags             = var.resource_tags

  environment {
    variables = {
      ATHENA_DATABASE = "uk_snowfall_processed"
      S3_BUCKET_NAME  = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      WORKGROUP_NAME  = "uk-snowfall-pipeline"
      SNS_TOPIC_ARN   = var.sns_topic_arn
    }
  }
}

# CloudWatch Event Rule to trigger Lambda daily at 1:30 AM UTC
resource "aws_cloudwatch_event_rule" "service_agent_server_extract_schedule" {
  name                = "uk-snowfall-service-agent-server-extract-schedule"
  description         = "Triggers the service agent server extract Lambda daily at 1:30 AM UTC"
  schedule_expression = "cron(30 1 * * ? *)"
}

# Add Lambda as the Target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_service_agent_server_extract_lambda" {
  rule      = aws_cloudwatch_event_rule.service_agent_server_extract_schedule.name
  target_id = "service-agent-server-extract-target"
  arn       = aws_lambda_function.service_agent_server_extract_function.arn
}

# Grant EventBridge Permission to Invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_service_agent_server_extract" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.service_agent_server_extract_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.service_agent_server_extract_schedule.arn
  depends_on    = [aws_lambda_function.service_agent_server_extract_function, aws_cloudwatch_event_rule.service_agent_server_extract_schedule]

}



##########################################################################MERAKI-CLIENT-INFO-FETCH###################################################

# Archive the meraki_client_info Python script
data "archive_file" "meraki_client_info" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/meraki-client-info/"
  output_path = "${path.module}/scripts/zips/meraki-client-info.zip"
}

# Lambda Function for fetching Meraki client info
resource "aws_lambda_function" "uk_snowfall_meraki_client_info_function" {
  filename      = "${path.module}/scripts/zips/meraki-client-info.zip"
  function_name = "uk-snowfall-meraki-client-info-${var.environment}"
  role          = var.role_assumed_arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  memory_size   = 10240
  ephemeral_storage {
    size = 10240
  }
  timeout          = 900 # 15 minutes
  description      = "Fetch client info from Meraki API and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/meraki-client-info.zip")
  tags             = var.resource_tags
  layers = [
    "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1",
    "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:15"
  ]
  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      TEMP_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-temp-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

# Lambda permission for S3
resource "aws_lambda_permission" "allow_landing_meraki_client_info_bucket" {
  statement_id  = "AllowExecutionFromS3BucketClientInfo"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_meraki_client_info_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on    = [var.landing_bucket_arn, aws_lambda_function.uk_snowfall_meraki_client_info_function]
}

# CloudWatch Event Rule to trigger Lambda
resource "aws_cloudwatch_event_rule" "meraki_client_info_schedule" {
  name                = "uk-snowfall-meraki-client-info-schedule"
  description         = "Triggers the Meraki client info Lambda function daily at 1 AM UTC-STOPPED FOR NOW "
  schedule_expression = "cron(0 1 * * ? *)"
}

# Add Lambda as the Target of the Event Rule
resource "aws_cloudwatch_event_target" "invoke_meraki_client_info_lambda" {
  rule      = aws_cloudwatch_event_rule.meraki_client_info_schedule.name
  target_id = "meraki-client-info-target"
  arn       = aws_lambda_function.uk_snowfall_meraki_client_info_function.arn
}

# Grant EventBridge Permission to Invoke the Lambda
resource "aws_lambda_permission" "allow_eventbridge_invoke_meraki_client_info" {
  statement_id  = "AllowExecutionFromEventBridgeClientInfo"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_meraki_client_info_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.meraki_client_info_schedule.arn
}

##########################################################################ODS-USER-DATA-TO-NCR###################################################

# Archive the Lambda source code
data "archive_file" "ods_user_data_to_datashare" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/ods-user-data-to-datashare/"
  output_path = "${path.module}/scripts/zips/ods-user-data-to-datashare.zip"
}

# Lambda function
resource "aws_lambda_function" "ods_user_data_to_datashare" {
  filename         = data.archive_file.ods_user_data_to_datashare.output_path
  function_name    = "uk-snowfall-ods-user-data-to-datashare-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Triggered by S3 to move ods_user_data CSV files to datashare bucket"
  source_code_hash = filebase64sha256(data.archive_file.ods_user_data_to_datashare.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      SOURCE_BUCKET = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

# Lambda permission to allow S3 to invoke it
resource "aws_lambda_permission" "allow_ods_user_data_to_datashare_s3" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ods_user_data_to_datashare.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.raw_bucket_arn

  depends_on = [
    aws_lambda_function.ods_user_data_to_datashare
  ]
}

# Reference to the raw bucket
data "aws_s3_bucket" "raw_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
}

# S3 event trigger for Lambda
# resource "aws_s3_bucket_notification" "ods_user_data_to_datashare_trigger" {
#   bucket = data.aws_s3_bucket.raw_bucket.id

#   lambda_function {
#     lambda_function_arn = aws_lambda_function.ods_user_data_to_datashare.arn
#     events              = ["s3:ObjectCreated:*"]
#     filter_prefix       = "ods/user_data"
#     filter_suffix       = ".csv"
#   }

#   depends_on = [
#     aws_lambda_permission.allow_ods_user_data_to_datashare_s3
#   ]
# }
############################################
## SNOWFALL PROACTIVE ALERTS
############################################

## Archive the snowfall-proactive-alerts Python script
data "archive_file" "uk_snowfall_proactive_alerts" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-alerts/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-alerts.zip"
}

## Lambda function - uk-snowfall-proactive-alerts
resource "aws_lambda_function" "uk_snowfall_proactive_alerts" {
  filename         = data.archive_file.uk_snowfall_proactive_alerts.output_path
  function_name    = "uk-snowfall-proactive-alerts-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Triggered by EventBridge schedule to run proactive alerts for Snowfall"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_alerts.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      DYNAMO_REGION            = "eu-central-1"
      RULES_TABLE              = "uk-snowfall-${var.environment}-incident-rules"
      PROACTIVE_ALERTS_TABLE   = "uk-snowfall-${var.environment}-proactive-alerts"
      RESULTS_TABLE_NAME       = "uk-snowfall-${var.environment}-proactive-websocket-connections-results"
      ATHENA_REGION            = "eu-central-1"
      ATHENA_OUTPUT_S3         = "s3://eu-central1-${var.environment}-uk-snowfall-temp-${var.account_number}/alerts/"
      SNS_TOPIC_ARN            = var.sns_topic_arn
      STAGE_NAME               = var.stage_name
      TABLE_NAME               = "uk-snowfall-${var.environment}-proactive-websocket-connections"
      SERVICENOW_TICKET_LAMBDA = aws_lambda_function.uk_snowfall_servicenow_proactive_ticket.function_name
    }
  }
}




############################################
## ServiceNow Proactive Ticket Creation Lambda
##  version - invoked async from snowfall-proactive-alerts
## Source: scripts/python/servicenow-proactive-ticket-creation/
############################################

data "archive_file" "uk_snowfall_servicenow_proactive_ticket" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/servicenow-proactive-ticket-creation/"
  output_path = "${path.module}/scripts/zips/servicenow-proactive-ticket-creation.zip"
}

resource "aws_lambda_function" "uk_snowfall_servicenow_proactive_ticket" {
  filename         = data.archive_file.uk_snowfall_servicenow_proactive_ticket.output_path
  function_name    = "uk-snowfall-servicenow-proactive-ticket-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 60
  description      = "Creates a ServiceNow ticket via NCR REST API for a single proactive alert"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_servicenow_proactive_ticket.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      SECRET_NAME               = "uk-snowfall-ncr-servicenow"
      SECRET_REGION             = "eu-central-1"
      NCR_VERIFY_SSL            = "false"
      SERVICE_NOW_TICKETS_TABLE = "uk-snowfall-${var.environment}-service-now-tickets"
      RULES_TABLE               = "uk-snowfall-${var.environment}-incident-rules"
      SOURCE_SYSTEM             = "WS"
      USER_ID                   = "UKMCD"
      COUNTRY_CODE              = "UK"
    }
  }
}

## Allow proactive-alerts Lambda to invoke this ticket-create Lambda
resource "aws_lambda_permission" "uk_snowfall_allow_proactive_alerts_to_invoke_servicenow_proactive_ticket" {
  statement_id  = "AllowProactiveAlertsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_servicenow_proactive_ticket.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.uk_snowfall_proactive_alerts.arn
}


############################################
## ServiceNow Proactive Ticket Sync Lambda
##  Scheduled hourly during business hours; reconciles open tickets in
##  the service-now-tickets DDB table against the NCR Athena view and
##  marks them closed when NCR has closed them.
## Source: scripts/python/servicenow-proactive-ticket-sync/
############################################

data "archive_file" "uk_snowfall_servicenow_proactive_ticket_sync" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/servicenow-proactive-ticket-sync/"
  output_path = "${path.module}/scripts/zips/servicenow-proactive-ticket-sync.zip"
}

resource "aws_lambda_function" "uk_snowfall_servicenow_proactive_ticket_sync" {
  filename         = data.archive_file.uk_snowfall_servicenow_proactive_ticket_sync.output_path
  function_name    = "uk-snowfall-servicenow-proactive-ticket-sync-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 300
  description      = "Reconciles open ServiceNow tickets against NCR Athena view and marks closed in DynamoDB"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_servicenow_proactive_ticket_sync.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      SERVICE_NOW_TICKETS_TABLE = "uk-snowfall-${var.environment}-service-now-tickets"
      ATHENA_DATABASE           = "uk_snowfall_semantic"
      ATHENA_VIEW               = "ncr_service_now_service_case_latest"
      ATHENA_WORKGROUP          = "uk-snowfall-pipeline"
      ATHENA_OUTPUT_S3          = "s3://eu-central1-${var.environment}-uk-snowfall-athena-${var.account_number}/close-sync/"
      ATHENA_REGION             = "eu-central-1"
      BATCH_SIZE                = "100"
      MAX_TICKETS_PER_RUN       = "500"
    }
  }
}

## EventBridge schedule: 15 min after upstream NCR ingest lands (06:45-20:45 GMT, weekdays)
resource "aws_cloudwatch_event_rule" "uk_snowfall_servicenow_proactive_ticket_sync_schedule" {
  name                = "uk-snowfall-servicenow-proactive-ticket-sync-schedule-${var.environment}"
  description         = "Run NCR ticket sync hourly at :45 past business hours weekdays (GMT)"
  schedule_expression = "cron(45 6-20 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "uk_snowfall_servicenow_proactive_ticket_sync_target" {
  rule      = aws_cloudwatch_event_rule.uk_snowfall_servicenow_proactive_ticket_sync_schedule.name
  target_id = "uk-snowfall-servicenow-proactive-ticket-sync"
  arn       = aws_lambda_function.uk_snowfall_servicenow_proactive_ticket_sync.arn
}

resource "aws_lambda_permission" "uk_snowfall_allow_eventbridge_to_invoke_proactive_ticket_sync" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_servicenow_proactive_ticket_sync.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.uk_snowfall_servicenow_proactive_ticket_sync_schedule.arn
}


## CloudWatch EventBridge schedule trigger
resource "aws_cloudwatch_event_rule" "uk_snowfall_proactive_alerts_schedule" {
  name                = "uk-snowfall-proactive-alerts-schedule-${var.environment}"
  description         = "Run proactive alerts check every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "uk_snowfall_proactive_alerts_target" {
  rule      = aws_cloudwatch_event_rule.uk_snowfall_proactive_alerts_schedule.name
  target_id = "uk-snowfall-proactive-alerts"
  arn       = aws_lambda_function.uk_snowfall_proactive_alerts.arn
}

resource "aws_lambda_permission" "uk_snowfall_allow_eventbridge_to_invoke_alerts" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_proactive_alerts.arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.uk_snowfall_proactive_alerts_schedule.arn
}



############################################
## DynamoDB: Incident Rules Table
############################################
resource "aws_dynamodb_table" "uk_snowfall_incident_rules" {
  name         = "uk-snowfall-${var.environment}-incident-rules"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "rule_id"

  attribute {
    name = "rule_id"
    type = "S"
  }

  tags = var.resource_tags
}



############################################
## DynamoDB: ServiceNow Tickets Table
############################################
resource "aws_dynamodb_table" "uk_snowfall_service_now_tickets" {
  name         = "uk-snowfall-${var.environment}-service-now-tickets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticket_id"

  attribute {
    name = "ticket_id"
    type = "S"
  }
  tags = var.resource_tags
}


############################################
## DynamoDB: Proactive Alerts Table
############################################
resource "aws_dynamodb_table" "uk_snowfall_proactive_alerts" {
  name         = "uk-snowfall-${var.environment}-proactive-alerts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "alert_id"

  attribute {
    name = "alert_id"
    type = "S"
  }

  tags = var.resource_tags
}


############################################
## SNOWFALL PROACTIVE DYNAMODB RULES
############################################

## Archive the snowfall-proactive-dynamodb-rules Python script
data "archive_file" "uk_snowfall_proactive_dynamodb_rules" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-dynamodb-rules/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-dynamodb-rules.zip"
}

## Lambda function - snowfall-proactive-dynamodb-rules
resource "aws_lambda_function" "uk_snowfall_proactive_dynamodb_rules" {
  filename         = data.archive_file.uk_snowfall_proactive_dynamodb_rules.output_path
  function_name    = "uk-snowfall-proactive-dynamodb-rules-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 512
  timeout          = 120
  description      = "Lambda to insert proactive incident rules into DynamoDB for Snowfall"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_dynamodb_rules.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      DYNAMO_REGION = "eu-central-1"
      RULES_TABLE   = "uk-snowfall-${var.environment}-incident-rules"
      NUM_RULES     = "10"
    }
  }
}

resource "null_resource" "invoke_lambda_once" {
  provisioner "local-exec" {
    command = <<EOT
      aws lambda invoke \
        --function-name uk-snowfall-proactive-dynamodb-rules-${var.environment} \
        --payload '{}' \
        ${path.module}/lambda_response.json
    EOT
  }

  depends_on = [aws_lambda_function.uk_snowfall_proactive_dynamodb_rules]
}


############################################
## DynamoDB: WebSocket Connections Table
############################################
resource "aws_dynamodb_table" "websocket_connections" {
  name         = "uk-snowfall-${var.environment}-proactive-websocket-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "restaurant_number"
  range_key    = "device_id"

  attribute {
    name = "restaurant_number"
    type = "S"
  }

  attribute {
    name = "device_id"
    type = "S"
  }

  tags = var.resource_tags
}

############################################
## DynamoDB: WebSocket Connections Results
############################################
resource "aws_dynamodb_table" "websocket_connections_results" {
  name         = "uk-snowfall-${var.environment}-proactive-websocket-connections-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "result_id"
  range_key    = "device_id"

  attribute {
    name = "result_id"
    type = "S"
  }

  attribute {
    name = "device_id"
    type = "S"
  }

  tags = var.resource_tags
}

############################################
## PROACTIVE HEALING LAMBDA FUNCTIONS
############################################

############################################
## Archive: Connect Handler
############################################
data "archive_file" "uk_snowfall_proactive_healing_connect" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-connect/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-connect.zip"
}

############################################
## Lambda: Connect Handler
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_connect" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_connect.output_path
  function_name    = "uk-snowfall-proactive-healing-connect-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 29
  description      = "Handles WebSocket $connect events for Snowfall Proactive Healing"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_connect.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      TABLE_NAME = "uk-snowfall-${var.environment}-proactive-websocket-connections"
    }
  }
}

############################################
## Archive: Disconnect Handler
############################################
data "archive_file" "uk_snowfall_proactive_healing_disconnect" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-disconnect/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-disconnect.zip"
}

############################################
## Lambda: Disconnect Handler
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_disconnect" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_disconnect.output_path
  function_name    = "uk-snowfall-proactive-healing-disconnect-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 29
  description      = "Handles WebSocket $disconnect events for Snowfall Proactive Healing"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_disconnect.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      TABLE_NAME = "uk-snowfall-${var.environment}-proactive-websocket-connections"
    }
  }
}

############################################
## Archive: Default Handler
############################################
data "archive_file" "uk_snowfall_proactive_healing_default" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-default/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-default.zip"
}

############################################
## Lambda: Default Handler
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_default" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_default.output_path
  function_name    = "uk-snowfall-proactive-healing-default-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 29
  description      = "Handles default WebSocket route for Snowfall Proactive Healing"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_default.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      TABLE_NAME         = "uk-snowfall-${var.environment}-proactive-websocket-connections"
      RESULTS_TABLE_NAME = "uk-snowfall-${var.environment}-proactive-websocket-connections-results"
      STAGE_NAME         = var.stage_name
    }
  }
}

############################################
## Archive: Monitor Handler
############################################
data "archive_file" "uk_snowfall_proactive_healing_monitor" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-monitor/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-monitor.zip"
}

############################################
## Lambda: Monitor Handler
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_monitor" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_monitor.output_path
  function_name    = "uk-snowfall-proactive-healing-monitor-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 29
  description      = "Monitors Snowfall Proactive Healing and triggers notifier workflows"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_monitor.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      TABLE_NAME    = "uk-snowfall-${var.environment}-proactive-websocket-connections"
      STALE_TIMEOUT = "30m"
    }
  }
}




############################################
## Archive: JWT Authorizer (Proactive Healing)
############################################
data "archive_file" "uk_snowfall_proactive_healing_jwt_authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-jwt-authorizer/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-jwt-authorizer.zip"
}

############################################
## Lambda: JWT Authorizer (Proactive Healing)
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_jwt_authorizer" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_jwt_authorizer.output_path
  function_name    = "uk-snowfall-proactive-healing-jwt-authorizer-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10
  description      = "JWT authorizer for Snowfall Proactive Healing APIs/WebSocket"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_jwt_authorizer.output_path)
  tags             = var.resource_tags
  layers = [
    var.jwt_layer_arn
  ]



  environment {
    variables = {
      TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}


############################################
## Permissions: Allow  Lambda to read from s3
############################################
resource "aws_lambda_permission" "allow_proactive_healing_jwt_authorizer_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_proactive_healing_jwt_authorizer.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.service_agent_bucket_arn
  depends_on = [
    aws_lambda_function.uk_snowfall_proactive_healing_jwt_authorizer
  ]
}


############################################
## Archive: JWT Authorizer (ThousandEyes Alerts)
############################################
data "archive_file" "uk_snowfall_thousandeyes_alerts_jwt_authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/thousandeyes-alerts-jwt-authorizer/"
  output_path = "${path.module}/scripts/zips/uk_snowfall_thousandeyes_alerts_jwt_authorizer.zip"
}

############################################
## Lambda: JWT Authorizer (ThousandEyes Alerts)
############################################
resource "aws_lambda_function" "uk_snowfall_thousandeyes_alerts_jwt_authorizer" {
  filename = data.archive_file.uk_snowfall_thousandeyes_alerts_jwt_authorizer.output_path

  # AWS Lambda function name (kebab-case for AWS)
  function_name    = "uk-snowfall-thousandeyes-alerts-jwt-authorizer-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10
  description      = "JWT authorizer for ThousandEyes Alerts APIs"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_thousandeyes_alerts_jwt_authorizer.output_path)
  tags             = var.resource_tags

  layers = [
    var.jwt_layer_arn
  ]



  ############################################
  ## Environment variables
  ############################################
  environment {
    variables = {
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

############################################
## Archive: ThousandEyes Alerts Lambda
############################################
data "archive_file" "uk_snowfall_thousandeyes_alerts" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/thousandeyes-alerts/"
  output_path = "${path.module}/scripts/zips/uk_snowfall_thousandeyes_alerts.zip"
}

############################################
## Lambda: ThousandEyes Alerts Processor
############################################
resource "aws_lambda_function" "uk_snowfall_thousandeyes_alerts" {
  filename = data.archive_file.uk_snowfall_thousandeyes_alerts.output_path

  # AWS Lambda function name (kebab-case for AWS)
  function_name    = "uk-snowfall-thousandeyes-alerts-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10
  description      = "Processes ThousandEyes alert payloads and writes ticket entries to DynamoDB"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_thousandeyes_alerts.output_path)
  tags             = var.resource_tags



  ############################################
  ## Environment variables
  ############################################
  environment {
    variables = {
      TABLE_NAME = "uk-snowfall-${var.environment}-thousandeyes-alerts"
    }
  }
}


############################################
## DynamoDB: ThousandEyes Alerts
############################################
resource "aws_dynamodb_table" "thousandeyes_alerts" {
  name         = "uk-snowfall-${var.environment}-thousandeyes-alerts"
  billing_mode = "PAY_PER_REQUEST"

  # TODO: update to restaurant_number (PK) + alert_id (SK) when real alerts configured
  hash_key = "alert_id"

  # hash_key  = "restaurant_number"
  # range_key = "alert_id"

  ############################################
  ## Attributes
  ############################################
  attribute {
    name = "alert_id"
    type = "S"
  }

  # attribute {
  #   name = "restaurant_number"
  #   type = "S"
  # }

  ############################################
  ## Tags
  ############################################
  tags = var.resource_tags
}



