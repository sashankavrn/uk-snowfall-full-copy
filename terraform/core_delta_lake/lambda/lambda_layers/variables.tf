variable "layer_name" {
  type        = string
  description = "Lambda layer name"
}

variable "description" {
  type        = string
  default     = "JWT dependencies for Lambda"
}

variable "compatible_runtimes" {
  type        = list(string)
  default     = ["python3.12"]
}
