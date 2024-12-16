variable "resource_tags" {
  description = "Common tags to apply to resources"
  type        = map(string)
}

variable "glue_job_name" {
  description = "The name of the Glue job to be used in triggers"
  type        = string
}

