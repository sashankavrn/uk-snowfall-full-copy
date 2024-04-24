resource "aws_glue_workflow" "change_request" {
  name = "uk-snowfall-change-request"
  tags = var.resource_tags
  description = "Workflow for the change-request data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "change_request"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "change_request" {
  name = "uk-snowfall-change-request-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.change_request.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}