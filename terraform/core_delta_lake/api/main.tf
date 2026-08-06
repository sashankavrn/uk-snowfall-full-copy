

############################################
## REST API-service-agent-api
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
  authorizer_uri  = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.service_agent_upload_s3_jwt_authorizer_arn}/invocations"

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
  uri                     = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.service_agent_upload_s3_arn}/invocations"

}

############################################
## DEPLOYMENT
############################################



resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.rest_api.id

  triggers = {
   redeploy = sha1(jsonencode({
     rest_api     = aws_api_gateway_rest_api.rest_api.id
     # authorizer   = aws_api_gateway_authorizer.jwt_auth.id
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
    # aws_api_gateway_authorizer.jwt_auth
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
  statement_id = "AllowExecutionFromAPIGatewayUpload"
  action       = "lambda:InvokeFunction"
  # function_name = data.aws_lambda_function.service_agent.function_name
  function_name = var.service_agent_upload_s3_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

# Allow API Gateway to invoke the JWT authorizer Lambda
resource "aws_lambda_permission" "api_gateway_authorizer" {
  statement_id = "AllowExecutionFromAPIGatewayAuthorizer"
  action       = "lambda:InvokeFunction"
  # function_name = data.aws_lambda_function.service_agent_upload_s3_jwt_authorizer.function_name
  function_name = var.service_agent_upload_s3_jwt_authorizer_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.rest_api.execution_arn}/*/*"
}

############################################
## REST API - thousandeyes-api
############################################

resource "aws_api_gateway_rest_api" "thousandeyes_api" {
  name        = "uk-snowfall-thousandeyes-api-${var.environment}"
  description = "REST API for ThousandEyes Alerts"
  tags        = var.resource_tags
}

############################################
## JWT AUTHORIZER
############################################

resource "aws_api_gateway_authorizer" "thousandeyes_jwt_auth" {
  name            = "thousandeyes-jwt-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.thousandeyes_api.id
  type            = "TOKEN"
  identity_source = "method.request.header.Authorization"

  authorizer_uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.thousandeyes_alerts_jwt_authorizer_arn}/invocations"
}

############################################
## /alert RESOURCE
############################################

resource "aws_api_gateway_resource" "thousandeyes_alert" {
  rest_api_id = aws_api_gateway_rest_api.thousandeyes_api.id
  parent_id   = aws_api_gateway_rest_api.thousandeyes_api.root_resource_id
  path_part   = "alert"
}

############################################
## POST /alert METHOD
############################################

resource "aws_api_gateway_method" "thousandeyes_post_alert" {
  rest_api_id   = aws_api_gateway_rest_api.thousandeyes_api.id
  resource_id   = aws_api_gateway_resource.thousandeyes_alert.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.thousandeyes_jwt_auth.id
}

############################################
## INTEGRATION → TICKET LAMBDA
############################################

resource "aws_api_gateway_integration" "thousandeyes_ticket_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.thousandeyes_api.id
  resource_id             = aws_api_gateway_resource.thousandeyes_alert.id
  http_method             = aws_api_gateway_method.thousandeyes_post_alert.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"

  uri = "arn:aws:apigateway:eu-central-1:lambda:path/2015-03-31/functions/${var.thousandeyes_alerts_arn}/invocations"
}

############################################
## DEPLOYMENT (UNIQUE NAME)
############################################

resource "aws_api_gateway_deployment" "thousandeyes_deployment" {
  rest_api_id = aws_api_gateway_rest_api.thousandeyes_api.id

  triggers = {
    redeploy = sha1(jsonencode({
      rest_api    = aws_api_gateway_rest_api.thousandeyes_api.id
      method_post = aws_api_gateway_method.thousandeyes_post_alert.id
      integration = aws_api_gateway_integration.thousandeyes_ticket_lambda.id
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.thousandeyes_ticket_lambda,
    aws_api_gateway_method.thousandeyes_post_alert
  ]
}

############################################
## STAGE (UNIQUE NAME)
############################################

resource "aws_api_gateway_stage" "thousandeyes_stage" {
  deployment_id = aws_api_gateway_deployment.thousandeyes_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.thousandeyes_api.id
  stage_name    = var.stage_name
  tags          = var.resource_tags
}

############################################
## LAMBDA PERMISSIONS (UNIQUE NAMES)
############################################

resource "aws_lambda_permission" "thousandeyes_api_gateway_ticket" {
  statement_id  = "AllowExecutionFromAPIGatewayTicketThousandEyes"
  action        = "lambda:InvokeFunction"
  function_name = var.thousandeyes_alerts_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.thousandeyes_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "thousandeyes_api_gateway_authorizer" {
  statement_id  = "AllowExecutionFromAPIGatewayAuthorizerThousandEyes"
  action        = "lambda:InvokeFunction"
  function_name = var.thousandeyes_alerts_jwt_authorizer_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.thousandeyes_api.execution_arn}/*/*"
}
