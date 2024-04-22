resource "aws_glue_workflow" "problem_record" {
  name = "uk-snowfall-problem-record"
  tags = var.resource_tags
  description = "Workflow for the problem record data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "problem_record"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "problem_record" {
  name = "uk-snowfall-problem-record-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.problem_record.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}