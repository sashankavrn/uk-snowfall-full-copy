output "datashare_landing_bucket_name" {
  value       = module.datashare_buckets.datashare_landing_bucket_name
  description = "The Name for the Datashare Landing bucket"
}

output "datashare_landing_bucket_arn" {
  value       = module.datashare_buckets.datashare_landing_bucket_arn
  description = "The ARN for the Datashare Landing bucket"
}

output "datashare_processed_bucket_name" {
  value       = module.datashare_buckets.datashare_processed_bucket_name
  description = "The Name for the Datashare Processed bucket"
}

output "datashare_processed_bucket_arn" {
  value       = module.datashare_buckets.datashare_processed_bucket_arn
  description = "The ARN for the Datashare Processed bucket"
}

output "datashare_landing_trigger_arn" {
  value       = module.datashare_lambda_module.datashare_landing_trigger_lambda_arn
  description = "The ARN for the Datashare Landing Trigger Lambda"
}
