variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
}

variable "lambda_function_arn" {
  description = "ARN of the Lambda function to be triggered"
  type        = string
}

variable "aws_role_to_assume" {
  description = "ARN of the IAM role to assume"
  type        = string
}

variable "processing_lambda_arn" {
  description = "ARN of the processing Lambda function"
  type        = string
}