############################################
## PROACTIVE HEALING: API Gateway Outputs
############################################

output "proactive_healing_websocket_api_id" {
  description = "The ID of the Proactive Healing WebSocket API Gateway"
  value       = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.id
}

output "proactive_healing_websocket_stage_name" {
  description = "The name of the Proactive Healing WebSocket API stage"
  value       = aws_apigatewayv2_stage.uk_snowfall_proactive_healing_websocket_stage.name
}

output "proactive_healing_websocket_api_endpoint" {
  description = "The WebSocket API endpoint URL for Proactive Healing"
  value       = aws_apigatewayv2_api.uk_snowfall_proactive_healing_websocket_api.api_endpoint
}
output "websocket_endpoint" {
  value = aws_apigatewayv2_stage.uk_snowfall_proactive_healing_websocket_stage.invoke_url
}
