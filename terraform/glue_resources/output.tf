output "workflow_trigger_arns" {
  description = "A map of workflow trigger ARNs for each Glue Workflow"
  value       = module.workflows.workflow_trigger_arns
}
