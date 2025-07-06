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

#Lambda for creating athena views
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
      S3_BUCKET_NAME = "eu-central1-${var.environment}-uk-snowfall-artifact-${var.account_number}"
      WORKGROUP_NAME = "uk-snowfall-pipeline"
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
  depends_on = [ var.artifact_bucket_arn,aws_lambda_function.uk_snowfall_create_athena_views ]
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
    role            = var.role_assumed_arn
    handler         = "lambda_function.lambda_handler"
    runtime         = "python3.12"
    memory_size     = 2048
    timeout         = 720
    description     = "Fetch data from New Relic API and update to landing bucket"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/newrelic-rmp-fetch-device.zip")
    tags            = var.resource_tags
    layers = [
      "arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1", # AWS SDK for Pandas
      "arn:aws:lambda:eu-central-1:770693421928:layer:Klayers-p312-requests:4"   # Requests library
    ]
    environment {
      variables = {
        TARGET_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
        SNS_TOPIC_ARN   = var.sns_topic_arn
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
 schedule_expression = "cron(0 1 * * ? *)"  # Runs at 1 AM UTC every day
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
  memory_size      = 4096                     # Increased 
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
      TARGET_BUCKET   = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      SNS_TOPIC_ARN = var.sns_topic_arn
      
    }
  }
}



# CloudWatch Event Rule to trigger Lambda every 2 minutes
resource "aws_cloudwatch_event_rule" "newrelic_metrics_lambda_schedule" {
  name                = "uk-snowfall-newrelic-rmp-device-metrics-schedule"
  description         = "Triggers the New Relic device metrics Lambda every 2 minutes"
  schedule_expression = "rate(10 minutes)"
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
  depends_on    = [
    aws_lambda_function.newrelic_digital_gma_foe_response_function
  ]
}

resource "aws_cloudwatch_event_rule" "newrelic_digital_gma_foe_response_lambda_schedule" {
  name                = "uk-snowfall-newrelic-digital-gma-foe-response-schedule"
  description         = "Triggers the Lambda function every hour at 5 minutes past the hour"
  schedule_expression = "cron(5 * * * ? *)"
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
  handler          = "lambda_function.lambda_handler"  # Make sure this matches the Python file inside the ZIP
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
  schedule_expression = "cron(5 * * * ? *)"
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

############################################ SERVICE AGENT JWT/UPLOAD S3 LAMBDA #############################################

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
  description      = "Upload data to S3 using JWT authentication"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-upload-s3.zip")
  tags             = var.resource_tags
  layers = [  ]
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


############################################ SERVICE AGENT SERVER EXTRACT & UPLOAD TO S3 LAMBDA #############################################

# Archive the Lambda script for extracting service agent server info
data "archive_file" "service_agent_server_extract_script" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-server-extract/"
  output_path = "${path.module}/scripts/zips/service-agent-server-extract.zip"
}

# Lambda Function to extract service agent server info from Athena
resource "aws_lambda_function" "service_agent_server_extract_function" {
  filename         = "${path.module}/scripts/zips/service-agent-server-extract.zip"
  function_name    = "uk-snowfall-service-agent-server-extract-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 1024
  timeout          = 300
  description      = "Extracts service agent server information from Athena and stores it in S3"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/service-agent-server-extract.zip")
  tags             = var.resource_tags

  environment {
    variables = {
      ATHENA_DATABASE  = "uk_snowfall_processed"
      S3_BUCKET_NAME   = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
      WORKGROUP_NAME   = "uk-snowfall-pipeline"
      SNS_TOPIC_ARN    = var.sns_topic_arn
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
  depends_on = [aws_lambda_function.service_agent_server_extract_function, aws_cloudwatch_event_rule.service_agent_server_extract_schedule]

}

############################################ SERVICE AGENT SERVER FILES #############################################

## Archive the service-agent-server-files Python script
data "archive_file" "service_agent_server_files" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/service-agent-server-files/"
  output_path = "${path.module}/scripts/zips/service-agent-server-files.zip"
}

## Lambda function - service-agent-server-files
resource "aws_lambda_function" "service_agent_server_files" {
  filename         = data.archive_file.service_agent_server_files.output_path
  function_name    = "uk-snowfall-service-agent-server-files-${var.environment}"
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
  depends_on    = [
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


##########################################################################MERAKI-CLIENT-INFO-FETCH###################################################

# Archive the meraki_client_info Python script
data "archive_file" "meraki_client_info" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/meraki_client_info/"
  output_path = "${path.module}/scripts/zips/meraki_client_info.zip"
}

# Lambda Function for fetching Meraki client info
resource "aws_lambda_function" "uk_snowfall_meraki_client_info_function" {
  filename         = "${path.module}/scripts/zips/meraki_client_info.zip"
  function_name    = "uk-snowfall-meraki-client-info-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  memory_size      = 4000
  ephemeral_storage {
    size = 2048
  }
  timeout          = 900  # 15 minutes
  description      = "Fetch client info from Meraki API and update to landing bucket"
  source_code_hash = filebase64sha256("${path.module}/scripts/zips/meraki_client_info.zip")
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
  description         = "Triggers the Meraki client info Lambda function daily at 1 AM UTC"
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
