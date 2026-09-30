variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, qa, prod)"
  type        = string
}

variable "lambda_package" {
  description = "Path to Lambda deployment package zip"
  type        = string
}
