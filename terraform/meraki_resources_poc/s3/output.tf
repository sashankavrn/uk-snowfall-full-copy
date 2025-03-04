output "raw_bucket_name" {
  description = "The name of the Raw S3 bucket"
  value       = aws_s3_bucket.raw_bucket.bucket
}

output "raw_bucket_arn" {
  description = "The ARN of the Raw S3 bucket"
  value       = aws_s3_bucket.raw_bucket.arn
}

output "landing_bucket_name" {
  description = "The name of the Landing S3 bucket"
  value       = aws_s3_bucket.landing_bucket.bucket
}

output "landing_bucket_arn" {
  description = "The ARN of the Landing S3 bucket"
  value       = aws_s3_bucket.landing_bucket.arn
}

output "processed_bucket_name" {
  description = "The name of the Processed S3 bucket"
  value       = aws_s3_bucket.processed_bucket.bucket
}

output "processed_bucket_arn" {
  description = "The ARN of the Processed S3 bucket"
  value       = aws_s3_bucket.processed_bucket.arn
}

# Handling Folder Keys (Fixing Iteration Issues)
output "raw_folder_key" {
  description = "The key for the Raw bucket's folder"
  value       = aws_s3_object.raw_folder.key
}

output "landing_folder_key" {
  description = "The key for the Landing bucket's folder"
  value       = aws_s3_object.landing_folder.key
}

output "processed_folder_key" {
  description = "The key for the Processed bucket's folder"
  value       = aws_s3_object.processed_folder.key
}
