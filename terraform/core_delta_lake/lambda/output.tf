output "landing_trigger_arn" {
  value = aws_lambda_function.uk_snowfall_landing_function.arn
  description = "The landing trigger function ARN number"
}

output "lambda_s3_permission" {
  value = aws_lambda_permission.allow_landing_bucket.id
  description = "The permission for lambda to accept s3 events"
}

output "athena_trigger_arn" {
  value = aws_lambda_function.uk_snowfall_create_athena_views.arn
  description = "Create Athena Views ARN"
}

output "lambda_s3_permission_athena" {
  value = aws_lambda_permission.allow_artifact_bucket.id
  description = "The permission for lambda to accept s3 events"
}

output "service_agent_arn" {
  value       = aws_lambda_function.uk_snowfall_service_agent_function.arn
  description = "The service agent trigger function ARN number"
}
