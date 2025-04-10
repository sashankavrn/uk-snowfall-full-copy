variable "resource_tags" {}
variable "environment" {}
variable account_number{}
variable "role_assumed_arn" {}
variable "terraform_bucket_name" {}
variable "datashare_processed_trigger_lambda_arn" {
  description = "The ARN of the Datashare Processed Trigger Lambda function"
  type        = string
}
