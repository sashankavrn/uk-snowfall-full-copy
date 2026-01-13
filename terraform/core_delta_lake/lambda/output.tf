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

output "ods_user_data_to_datashare_arn" {
  value       = aws_lambda_function.ods_user_data_to_datashare.arn
  description = "ARN of the Lambda function that processes ods_user_data CSV files and moves them to the datashare bucket"
}

output "ods_user_data_to_datashare_permission" {
  value       = aws_lambda_permission.allow_ods_user_data_to_datashare_s3.id
  description = "Permission ID allowing the raw bucket to invoke the ods_user_data_to_datashare Lambda function"
}

output "connect_lambda_arn" {
  value = aws_lambda_function.uk_snowfall_proactive_healing_connect.invoke_arn
}

output "disconnect_lambda_arn" {
  value = aws_lambda_function.uk_snowfall_proactive_healing_disconnect.invoke_arn
}

output "default_lambda_arn" {
  value = aws_lambda_function.uk_snowfall_proactive_healing_default.invoke_arn
}
