output "datashare_landing_trigger_lambda_arn" {
  value       = aws_lambda_function.datashare_landing_trigger.arn
  description = "The ARN of the Datashare Landing Trigger Lambda function"
}

output "datashare_landing_trigger_lambda_name" {
  value       = aws_lambda_function.datashare_landing_trigger.function_name
  description = "The Name of the Datashare Landing Trigger Lambda function"
}


output "datashare_processed_trigger_lambda_arn" {
  value       = aws_lambda_function.datashare_processed_trigger.arn
  description = "The ARN of the Datashare Processed Trigger Lambda function"
}

output "datashare_processed_trigger_lambda_name" {
  value       = aws_lambda_function.datashare_processed_trigger.function_name
  description = "The Name of the Datashare Processed Trigger Lambda function"
}

