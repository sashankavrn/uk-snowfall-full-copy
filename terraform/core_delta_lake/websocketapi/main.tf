############################################
## PROACTIVE HEALING: API Gateway WebSocket
############################################

resource "aws_apigatewayv2_api" "uk_snowfall_proactive_healing_websocket_api" {
  name                       = "uk-snowfall-proactive-healing-websocket-${var.environment}"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}

############################################
## PROACTIVE HEALING: WebSocket Routes
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
## PROACTIVE HEALING: Lambda Integrations
############################################

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_connect_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.uk_snowfall_proactive_healing_connect.invoke_arn
}

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_disconnect_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.uk_snowfall_proactive_healing_disconnect.invoke_arn
}

resource "aws_apigatewayv2_integration" "uk_snowfall_proactive_healing_default_integration" {
  api_id           = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.uk_snowfall_proactive_healing_default.invoke_arn
}

############################################
## PROACTIVE HEALING: WebSocket Stage
############################################

resource "aws_apigatewayv2_stage" "uk_snowfall_proactive_healing_websocket_stage" {
  api_id      = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
  name        = var.environment
  auto_deploy = true
}
