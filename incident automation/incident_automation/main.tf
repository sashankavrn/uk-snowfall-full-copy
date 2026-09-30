terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.33.0"
    }
  }

  backend "s3" {
    key     = "incident_automation/terraform.tfstate"
    region  = "eu-west-2"
    encrypt = true
  }
}

# DynamoDB Tables
resource "aws_dynamodb_table" "incident_rules" {
  name         = "${var.environment}_incident_rules"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "rule_id"

  attribute {
    name = "rule_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "service_now_tickets" {
  name         = "${var.environment}_service_now_tickets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticket_id"

  attribute {
    name = "ticket_id"
    type = "S"
  }
}

# Lambda Execution Role
resource "aws_iam_role" "lambda_exec" {
  name = "${var.environment}_lambda_exec_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# IAM Policies for Lambda (DynamoDB + Athena + Logs)
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_dynamodb_athena" {
  name = "${var.environment}_lambda_dynamodb_athena"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:*"]
        Resource = [
          aws_dynamodb_table.incident_rules.arn,
          aws_dynamodb_table.service_now_tickets.arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["athena:*", "glue:*", "s3:*"]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "incident_handler" {
  function_name = "${var.environment}_incident_handler"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.11"
  handler       = "lambda_function.lambda_handler"
  filename      = var.lambda_package

  environment {
    variables = {
      ENVIRONMENT = var.environment
    }
  }
}

# EventBridge Rule (trigger every 15 minutes)
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  name                = "${var.environment}_incident_handler_schedule"
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.lambda_schedule.name
  target_id = "incident-handler"
  arn       = aws_lambda_function.incident_handler.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.incident_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule.arn
}
