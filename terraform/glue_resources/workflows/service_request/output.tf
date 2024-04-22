output "service_request_workflow_trigger_arn" {
  value = aws_glue_workflow.service_request.arn
  description = "The workflow trigger function ARN number"
}
