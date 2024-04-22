output "trading_hours_workflow_trigger_arn" {
  value = aws_glue_workflow.trading_hours.arn
  description = "The workflow trigger function ARN number"
}
