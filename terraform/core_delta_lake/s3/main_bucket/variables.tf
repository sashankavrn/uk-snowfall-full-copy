variable "resource_tags" {}
variable "environment" {}
variable "account_number" {}
variable "role_assumed_arn" {}
variable "lambda_landing_func_arn" {}
variable "lambda_permission" {}

variable "ods_user_data_lambda_arn" {
  description = "ARN of the ods_user_data_to_datashare Lambda function"
  type        = string
}

variable "ods_user_data_lambda_permission" {
  description = "Permission ID for ods_user_data_to_datashare Lambda function"
  type        = string
}
