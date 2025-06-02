output "api_gateway_rest_api_id" {
  description = "The ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.rest_api.id
}

output "api_gateway_deployment_id" {
  description = "The ID of the API Gateway deployment"
  value       = aws_api_gateway_deployment.deployment.id
}

output "api_gateway_stage_name" {
  description = "The name of the API Gateway stage"
  value       = aws_api_gateway_stage.stage.stage_name
}

# output "api_key" {
#   description = "The API key for accessing the API"
#   value       = aws_api_gateway_api_key.upload_api_key.value
# }
