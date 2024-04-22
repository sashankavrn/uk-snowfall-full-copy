resource "aws_glue_workflow" "service_request" {
  name = "uk-snowfall-service-request"
  tags = var.resource_tags
  description = "Workflow for the Service Request data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "service_request"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "service_request" {
  name = "uk-snowfall-service-request-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.service_request.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}