output "landing_bucket_name" {
  value = module.s3_module_main.landing_bucket_name
  description = "The Name for the landing bucket"
}

output "landing_bucket_arn" {
  value = module.s3_module_main.landing_bucket_arn
  description = "The ARN for the Landing bucket"
}

output "processed_bucket_name" {
  value = module.s3_module_main.processed_bucket_name
  description = "The Name for the Processed bucket"
}

output "processed_bucket_bucket_arn" {
  value = module.s3_module_main.processed_bucket_bucket_arn
  description = "The ARN for the Processed bucket"
}

output "temporary_folder_path" {
  value = module.s3_module_main.temporary_folder_path
}

output "snowfall_topic_arn" {
  value = module.sns_module.snowfall_topic_arn
}

output "landing_trigger_arn" {
  value = module.lambda_module.landing_trigger_arn
}
