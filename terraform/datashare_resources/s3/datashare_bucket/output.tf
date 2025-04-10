output "datashare_landing_bucket_name" {
  value       = aws_s3_bucket.datashare_landing_bucket.id
  description = "The Name for the Datashare Landing bucket"
}

output "datashare_landing_bucket_arn" {
  value       = aws_s3_bucket.datashare_landing_bucket.arn
  description = "The ARN for the Datashare Landing bucket"
}

output "datashare_processed_bucket_name" {
  value       = aws_s3_bucket.datashare_processed_bucket.id
  description = "The Name for the Datashare Processed bucket"
}

output "datashare_processed_bucket_arn" {
  value       = aws_s3_bucket.datashare_processed_bucket.arn
  description = "The ARN for the Datashare Processed bucket"
}
