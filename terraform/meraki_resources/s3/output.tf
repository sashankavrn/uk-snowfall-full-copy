output "s3_bucket_name" {
  description = "The name of the created S3 bucket"
  value       = aws_s3_bucket.raw_bucket.bucket
}

output "s3_bucket_arn" {
  description = "The ARN of the created S3 bucket"
  value       = aws_s3_bucket.raw_bucket.arn
}

output "s3_folder_keys" {
  description = "List of created folders in the S3 bucket"
  value       = [for key in aws_s3_object.raw_folder : key.key]
}
