output "service_offering_workflow_trigger_arn" {
  value = aws_glue_workflow.service_offering.arn
  description = "The workflow trigger function ARN number"
}
