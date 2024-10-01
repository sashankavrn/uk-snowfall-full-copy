output "workflow_trigger_arns" {
  description = "A map of workflow trigger ARNs for each Glue Workflow"
  value = {
    for key, workflow in local.workflows :
    key => aws_glue_trigger.glue_triggers[key].arn
  }
}