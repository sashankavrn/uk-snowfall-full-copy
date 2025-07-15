output "landing_bucket_name" {
  value = aws_s3_bucket.landing_bucket.id
  description = "The Name for the landing bucket"
}

output "landing_bucket_arn" {
  value = aws_s3_bucket.landing_bucket.arn
  description = "The ARN for the Landing bucket"
}


output "raw_bucket_name" {
  value = aws_s3_bucket.raw_bucket.id
  description = "The Name for the Raw bucket"
}


output "raw_bucket_arn" {
  value = aws_s3_bucket.raw_bucket.arn
  description = "The ARN for the Raw bucket"
}


output "preparation_bucket_name" {
  value = aws_s3_bucket.preparation_bucket.id
  description = "The Name for the Preparation bucket"
}

output "preparation_bucket_bucket_arn" {
  value = aws_s3_bucket.preparation_bucket.arn
  description = "The ARN for the Preparation bucket"
}


output "processed_bucket_name" {
  value = aws_s3_bucket.processed_bucket.id
  description = "The Name for the Processed bucket"
}

output "processed_bucket_bucket_arn" {
  value = aws_s3_bucket.processed_bucket.arn
  description = "The ARN for the Processed bucket"
}

output "artifact_bucket_name" {
  value = aws_s3_bucket.artifact_bucket.id
  description = "The Name for the Artifact bucket"
}

output "artifact_bucket_bucket_arn" {
  value = aws_s3_bucket.artifact_bucket.arn
  description = "The ARN for the Artifact bucket"
}

output "temporary_folder_path" {
  value = "s3://${aws_s3_bucket.artifact_bucket.id}/${aws_s3_object.temporary_folder.key}"
}

# s3_module_main/outputs.tf
output "service_agent_bucket_arn" {
  description = "The ARN of the service agent S3 bucket"
  value       = aws_s3_bucket.service_agent_bucket.arn
}



output "rendered_policy" {
   value = data.template_file.bucket_policy.rendered
}



