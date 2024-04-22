output "sys_user_workflow_trigger_arn" {
  value = aws_glue_workflow.sys_user.arn
  description = "The workflow trigger function ARN number"
}
