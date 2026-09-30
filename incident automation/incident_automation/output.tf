output "dynamodb_incident_rules_table" {
  value = aws_dynamodb_table.incident_rules.name
}

output "dynamodb_service_now_tickets_table" {
  value = aws_dynamodb_table.service_now_tickets.name
}

output "lambda_function_name" {
  value = aws_lambda_function.incident_handler.function_name
}
