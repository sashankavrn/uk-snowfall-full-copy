output "sys_user_group_workflow_trigger_arn" {
  value = aws_glue_workflow.sys_user_group.arn
  description = "The workflow trigger function ARN number"
}
