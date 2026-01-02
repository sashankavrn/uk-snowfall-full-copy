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
      # JWT_SECRET = var.jwt_secret
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
      WEBSOCKET_ENDPOINT = var.websocket_endpoint
    }
  }
}

############################################
## Archive: Notifier Handler
############################################
data "archive_file" "uk_snowfall_proactive_healing_notifier" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/snowfall-proactive-healing-notifier/"
  output_path = "${path.module}/scripts/zips/snowfall-proactive-healing-notifier.zip"
}

############################################
## Lambda: Notifier Handler
############################################
resource "aws_lambda_function" "uk_snowfall_proactive_healing_notifier" {
  filename         = data.archive_file.uk_snowfall_proactive_healing_notifier.output_path
  function_name    = "uk-snowfall-proactive-healing-notifier-${var.environment}"
  role             = var.role_assumed_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 29
  description      = "Sends messages to WebSocket clients for Snowfall Proactive Healing"
  source_code_hash = filebase64sha256(data.archive_file.uk_snowfall_proactive_healing_notifier.output_path)
  tags             = var.resource_tags

  environment {
    variables = {
      TABLE_NAME = "uk-snowfall-${var.environment}-proactive-websocket-connections"
      WEBSOCKET_ENDPOINT = var.websocket_endpoint
    }
  }
}
