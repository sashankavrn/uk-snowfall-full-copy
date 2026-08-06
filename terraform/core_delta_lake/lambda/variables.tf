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
variable "smartsheet_6am_schedule" {}
variable "service_agent_bucket_arn" {}
variable "stage_name" {}
variable "ncr_soap_service_now_create_url" {
  type = string
}
variable "ncr_soap_service_now_update_url" {
  type = string
}
variable "jwt_layer_arn" {
  type = string
}
