output "lambda_landing_trigger" {
  value = module.lambda_landing_trigger.lambda_arn
}

output "lambda_processing_trigger" {
  value = module.lambda_processing_trigger.lambda_arn
}
