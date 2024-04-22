output "problem_record_workflow_trigger_arn" {
  value = aws_glue_workflow.problem_record.arn
  description = "The workflow trigger function ARN number"
}
