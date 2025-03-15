output "datasharing_landing_bucket_name" {
  value       = aws_s3_bucket.datasharing_landing_bucket.id
  description = "The Name for the Datasharing Landing bucket"
}

output "datasharing_landing_bucket_arn" {
  value       = aws_s3_bucket.datasharing_landing_bucket.arn
  description = "The ARN for the Datasharing Landing bucket"
}

output "datasharing_processed_bucket_name" {
  value       = aws_s3_bucket.datasharing_processed_bucket.id
  description = "The Name for the Datasharing Processed bucket"
}

output "datasharing_processed_bucket_arn" {
  value       = aws_s3_bucket.datasharing_processed_bucket.arn
  description = "The ARN for the Datasharing Processed bucket"
}
