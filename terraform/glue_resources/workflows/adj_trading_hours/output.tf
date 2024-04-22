output "adj_trading_hours_workflow_trigger_arn" {
  value = aws_glue_workflow.adj_trading_hours.arn
  description = "The workflow trigger function ARN number"
}
