resource "aws_glue_workflow" "sys_user" {
  name = "uk-snowfall-sys-user"
  tags = var.resource_tags
  description = "Workflow for the Sys User data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "sys_user"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "sys_user" {
  name = "uk-snowfall-sys-user-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.sys_user.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}