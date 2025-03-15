# Output the ARN of the Datashare Landing Trigger Lambda
output "datashare_landing_trigger_lambda_arn" {
  value       = aws_lambda_function.datashare_landing_trigger.arn
  description = "The ARN of the Datashare Landing Trigger Lambda function"
}

# Output the Name of the Datashare Landing Trigger Lambda
output "datashare_landing_trigger_lambda_name" {
  value       = aws_lambda_function.datashare_landing_trigger.function_name
  description = "The Name of the Datashare Landing Trigger Lambda function"
}

# Output the Permission for the Datashare Landing Trigger Lambda to Accept S3 Events
output "datashare_landing_trigger_lambda_s3_permission" {
  value       = aws_lambda_permission.allow_landing_trigger.id
  description = "The permission for the Datashare Landing Trigger Lambda to accept S3 events"
}

# # Output the ARN of the Datashare NCR Webhook Lambda (if enabled)
# output "datashare_ncr_webhook_lambda_arn" {
#   value       = aws_lambda_function.datashare_ncr_webhook.arn
#   description = "The ARN of the Datashare NCR Webhook Lambda function"
# }

# # Output the Name of the Datashare NCR Webhook Lambda (if enabled)
# output "datashare_ncr_webhook_lambda_name" {
#   value       = aws_lambda_function.datashare_ncr_webhook.function_name
#   description = "The Name of the Datashare NCR Webhook Lambda function"
# }

# # Output the Permission for Datashare NCR Webhook Lambda to Accept API Gateway Requests
# output "datashare_ncr_webhook_lambda_api_permission" {
#   value       = aws_lambda_permission.allow_ncr_webhook.id
#   description = "The permission for the Datashare NCR Webhook Lambda to accept API Gateway requests"
# }

# # Output the ARN of the Datashare Processed Trigger Lambda (if enabled)
# output "datashare_processed_trigger_lambda_arn" {
#   value       = aws_lambda_function.datashare_processed_trigger.arn
#   description = "The ARN of the Datashare Processed Trigger Lambda function"
# }

# # Output the Name of the Datashare Processed Trigger Lambda (if enabled)
# output "datashare_processed_trigger_lambda_name" {
#   value       = aws_lambda_function.datashare_processed_trigger.function_name
#   description = "The Name of the Datashare Processed Trigger Lambda function"
# }

# # Output the Permission for Datashare Processed Trigger Lambda to Accept S3 Events
# output "datashare_processed
