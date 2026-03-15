variable "resource_tags" {}
variable "environment" {}
variable "role_assumed_arn" {}
variable "landing_bucket_arn" {}
variable "raw_bucket_arn" {}
variable "sns_topic_arn" {}
variable "account_number" {}
variable "artifact_bucket_arn" {}
variable "meraki_schedule" {}
variable "newrelic_10min_schedule" {}
variable "newrelic_5min_schedule" {}
variable "newrelic_1am_schedule" {}
variable "service_agent_bucket_arn"{}
variable "stage_name" {}


variable "layer_name" {
  type        = string
  description = "Lambda layer name"
  default     = "jwt_layer"
}

variable "description" {
  type        = string
  default     = "JWT dependencies for Lambda"
}

variable "compatible_runtimes" {
  type        = list(string)
  default     = ["python3.12"]
}
