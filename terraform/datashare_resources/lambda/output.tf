output "datashare_landing_trigger_lambda_arn" {
  value       = aws_lambda_function.datashare_landing_trigger.arn
  description = "The ARN of the Datashare Landing Trigger Lambda function"
}

output "datashare_landing_trigger_lambda_name" {
  value       = aws_lambda_function.datashare_landing_trigger.function_name
  description = "The Name of the Datashare Landing Trigger Lambda function"
}

output "datashare_landing_trigger_lambda_s3_permission" {
  value       = aws_lambda_permission.allow_landing_trigger.id
  description = "The permission ID for the Datashare Landing Trigger Lambda to accept S3 events"
}

output "datashare_processed_trigger_lambda_arn" {
  value       = aws_lambda_function.datashare_processed_trigger.arn
  description = "The ARN of the Datashare Processed Trigger Lambda function"
}

output "datashare_processed_trigger_lambda_name" {
  value       = aws_lambda_function.datashare_processed_trigger.function_name
  description = "The Name of the Datashare Processed Trigger Lambda function"
}

output "datashare_processed_trigger_lambda_s3_permission" {
  value       = aws_lambda_permission.allow_processed_trigger.id
  description = "The permission ID for the Datashare Processed Trigger Lambda to accept S3 events"
}

# output "datashare_ncr_webhook_lambda_arn" {
#   value       = aws_lambda_function.datashare_ncr_webhook.arn
#   description = "The ARN of the Datashare NCR Webhook Lambda function"
# }

# output "datashare_ncr_webhook_lambda_name" {
#   value       = aws_lambda_function.datashare_ncr_webhook.function_name
#   description = "The Name of the Datashare NCR Webhook Lambda function"
# }

# output "datashare_ncr_webhook_lambda_s3_permission" {
#   value       = aws_lambda_permission.allow_ncr_webhook.id
#   description = "The permission ID for the Datashare NCR Webhook Lambda to accept S3 events"
# }
