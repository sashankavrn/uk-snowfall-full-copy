resource "aws_glue_workflow" "trading_hours" {
  name = "uk-snowfall-trading-hours"
  tags = var.resource_tags
  description = "Workflow for the trading hours data"
  max_concurrent_runs = 1
  default_run_properties = {

    "DATASET"                = "trading_hours"
    "GROUP"                  = "preparation"
  }
}


resource "aws_glue_trigger" "trading_hours" {
  name = "uk-snowfall-trading-hours-trigger"
  type = "EVENT"
  enabled = true
  workflow_name = aws_glue_workflow.trading_hours.name

  actions {
    job_name = var.glue_job_name
  }

  event_batching_condition {
    batch_size = 100
    batch_window = 10
  }
}