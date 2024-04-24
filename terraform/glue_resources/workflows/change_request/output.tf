output "change_request_workflow_trigger_arn" {
  value = aws_glue_workflow.change_request.arn
  description = "The workflow trigger function ARN number"
}
