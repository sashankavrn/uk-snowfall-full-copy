variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "database_name" {
  description = "Glue database name"
  type        = string
}

variable "table_prefix" {
  description = "Prefix for the table name"
  type        = string
}

variable "s3_path" {
  description = "S3 path for the Glue Crawler to scan"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket containing the data"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "resource_tags" {
  description = "Tags for resources"
  type        = map(string)
  default     = {}
}
