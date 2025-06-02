# API Gateway REST API
resource "aws_api_gateway_rest_api" "rest_api" {
  name        = "uk-snowfall-service-agent-api-${var.environment}"
  description = "REST API for uploading files"
}

# /upload resource
resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  parent_id   = aws_api_gateway_rest_api.rest_api.root_resource_id
  path_part   = "upload"
}

# POST method
resource "aws_api_gateway_method" "post" {
  rest_api_id      = aws_api_gateway_rest_api.rest_api.id
  resource_id      = aws_api_gateway_resource.upload.id
  http_method      = "POST"
  authorization    = "NONE"
  # api_key_required = true
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rest_api.id
  resource_id             = aws_api_gateway_resource.upload.id
  http_method             = aws_api_gateway_method.post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "${var.service_agent_func_arn}/invocations"

  depends_on = [
    module.lambda_module
  ]
}



# API deployment
resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  depends_on = [
    aws_api_gateway_integration.lambda
  ]
}

# API stage
resource "aws_api_gateway_stage" "stage" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  stage_name    = var.stage_name
}

# # Lambda permission for API Gateway
# resource "aws_lambda_permission" "api_gateway" {
#   statement_id  = "AllowExecutionFromAPIGateway"
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.upload_xml.function_name
#   principal     = "apigateway.amazonaws.com"
#   source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
# }

# # API Key
# resource "aws_api_gateway_api_key" "upload_api_key" {
#   name        = "UploadAPIKey-${var.stage_name}"
#   description = "API Key for XML upload"
#   enabled     = true
# }

# # Usage Plan with parameters
# resource "aws_api_gateway_usage_plan" "upload_plan" {
#   name = "UploadUsagePlan-${var.stage_name}"

#   api_stages {
#     api_id = aws_api_gateway_rest_api.rest_api.id
#     stage  = aws_api_gateway_stage.stage.stage_name
#   }

#   throttle_settings {
#     rate_limit  = var.rate_limit
#     burst_limit = var.burst_limit
#   }

#   quota_settings {
#     limit  = var.quota_limit
#     period = var.quota_period
#   }
# }

# # Attach API Key to Usage Plan
# resource "aws_api_gateway_usage_plan_key" "upload_plan_key" {
#   key_id        = aws_api_gateway_api_key.upload_api_key.id
#   key_type      = "API_KEY"
#   usage_plan_id = aws_api_gateway_usage_plan.upload_plan.id
# }
