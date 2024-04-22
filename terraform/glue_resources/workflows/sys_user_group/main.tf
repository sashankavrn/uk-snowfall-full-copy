resource "aws_glue_workflow" "sys_user_group" {
  name = "uk-snowfall-sys-user-group"
  tags = var.resource_tags
  description = "Workflow for the sys_user_group data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "sys_user_group"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "sys_user_group" {
  name = "uk-snowfall-sys-user-group-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.sys_user_group.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}