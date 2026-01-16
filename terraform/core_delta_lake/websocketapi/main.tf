############################################
## PROACTIVE HEALING: WebSocket API
############################################

resource "aws_apigatewayv2_api" "uk_snowfall_proactive_healing_websocket_api" {
  name                       = "uk-snowfall-proactive-healing-websocket-${var.environment}"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}

############################################
## ROUTES
############################################

resource "aws_apigatewayv2_route" "uk_snowfall_proactive_healing_connect_route" {
  api_id    = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.uk_snowfall_proactive_healing_connect_integration.id}"
}

resource "aws_apigatewayv2_route" "uk_snowfall_proactive_healing_disconnect_route" {
  api_id    = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.uk_snowfall_proactive_healing_disconnect_integration.id}"
}

resource "aws_apigatewayv2_route" "uk_snowfall_proactive_healing_default_route" {
  api_id    = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.uk_snowfall_proactive_healing_default_integration.id}"
}

############################################
## INTEGRATIONS (Using Passed‑In Lambda ARNs)
############################################

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_connect_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.connect_lambda_arn
}

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_disconnect_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.disconnect_lambda_arn
}

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_default_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.default_lambda_arn
}

# ############################################
# ## STAGE
# ############################################

# resource "aws_apigatewayv2_stage" "uk_snowfall_proactive_healing_websocket_stage" {
#   api_id      = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
#   name        = var.stage_name
#   auto_deploy = true
# }

############################################
## CLOUDWATCH LOG GROUP
############################################

resource "aws_cloudwatch_log_group" "uk_snowfall_proactive_healing_websocket_logs" {
  name              = "/aws/apigatewayv2/uk-snowfall-proactive-healing-websocket-${var.environment}"
  retention_in_days = 30
}

############################################
## STAGE (WITH CLOUDWATCH LOGGING)
############################################

resource "aws_apigatewayv2_stage" "uk_snowfall_proactive_healing_websocket_stage" {
  api_id      = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  name        = var.stage_name
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.uk_snowfall_proactive_healing_websocket_logs.arn

    format = jsonencode({
      requestId         = "$context.requestId"
      eventType         = "$context.eventType"
      routeKey          = "$context.routeKey"
      status            = "$context.status"
      integrationStatus = "$context.integrationStatus"
      connectionId      = "$context.connectionId"
      requestTime       = "$context.requestTime"
      errorMessage      = "$context.error.message"
    })
  }
}
