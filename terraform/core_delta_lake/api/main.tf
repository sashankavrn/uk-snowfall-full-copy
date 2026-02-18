

############################################
## LAMBDA DATA SOURCES
############################################

# # Upload Lambda
# data "aws_lambda_function" "service_agent" {
#   function_name = "uk-snowfall-service-agent-upload-s3-${var.environment}"
# }

# # JWT Authorizer Lambda
# data "aws_lambda_function" "service_agent_upload_s3_jwt_authorizer" {
#   function_name = "uk-snowfall-service-agent-upload-s3-jwt-authorizer-${var.environment}"
# }

############################################
## REST API
############################################

resource "aws_api_gateway_rest_api" "rest_api" {
  name        = "uk-snowfall-service-agent-api-${var.environment}"
  description = "REST API for uploading files"
}

############################################
## JWT AUTHORIZER
############################################

resource "aws_api_gateway_authorizer" "jwt_auth" {
  name            = "jwt-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.rest_api.id
  type            = "TOKEN"
  identity_source = "method.request.header.Authorization"
  authorizer_uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.service_agent_upload_s3_jwt_authorizer_arn}/invocations"


  # authorizer_uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${data.aws_lambda_function.service_agent_upload_s3_jwt_authorizer.arn}/invocations"
}

############################################
## /upload RESOURCE
############################################

resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id
  parent_id   = aws_api_gateway_rest_api.rest_api.root_resource_id
  path_part   = "upload"
}

############################################
## POST METHOD (USING JWT AUTHORIZER)
############################################

resource "aws_api_gateway_method" "post" {
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.jwt_auth.id
}

############################################
## INTEGRATION → UPLOAD LAMBDA
############################################

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.rest_api.id
  resource_id             = aws_api_gateway_resource.upload.id
  http_method             = aws_api_gateway_method.post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.service_agent_upload_s3_arn}/invocations"


  # uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${data.aws_lambda_function.service_agent.arn}/invocations"
}

############################################
## DEPLOYMENT
############################################

# resource "aws_api_gateway_deployment" "deployment" {
#   rest_api_id = aws_api_gateway_rest_api.rest_api.id

#   depends_on = [
#     aws_api_gateway_integration.lambda
#   ]
# }

resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  triggers = {
    redeploy = sha1(jsonencode({
      rest_api     = aws_api_gateway_rest_api.rest_api.id
      authorizer   = aws_api_gateway_authorizer.jwt_auth.id
      method_post  = aws_api_gateway_method.post.id
      integration  = aws_api_gateway_integration.lambda.id
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.lambda,
    aws_api_gateway_method.post,
    aws_api_gateway_authorizer.jwt_auth
  ]
}

############################################
## STAGE
############################################

resource "aws_api_gateway_stage" "stage" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.rest_api.id
  stage_name    = var.stage_name
}

############################################
## LAMBDA PERMISSIONS
############################################

# Allow API Gateway to invoke the upload Lambda
resource "aws_lambda_permission" "api_gateway_upload" {
  statement_id  = "AllowExecutionFromAPIGatewayUpload"
  action        = "lambda:InvokeFunction"
  # function_name = data.aws_lambda_function.service_agent.function_name
  function_name = var.service_agent_upload_s3_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

# Allow API Gateway to invoke the JWT authorizer Lambda
resource "aws_lambda_permission" "api_gateway_authorizer" {
  statement_id  = "AllowExecutionFromAPIGatewayAuthorizer"
  action        = "lambda:InvokeFunction"
  # function_name = data.aws_lambda_function.service_agent_upload_s3_jwt_authorizer.function_name
  function_name = var.service_agent_upload_s3_jwt_authorizer_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}
