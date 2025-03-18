# Define workflow details as reusable data in locals
locals {
  workflows = {
    "adj_trading_hours" = {
      name            = "uk-snowfall-adj-trading-hours"
      description     = "Workflow for the Adjusted Trading hours data"
      dataset         = "adj_trading_hours"
      group           = "preparation"
      trigger_name    = "uk-snowfall-adj-trading-hours-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "amazon_connect" = {
      name           = "uk-snowfall-amazon-connect"
      description    = "Workflow for the amazon_connect data"
      dataset        = "amazon_connect"
      group          = "preparation"
      trigger_name   = "uk-snowfall-amazon-connect-trigger"
      max_concurrent = 1
      batch_size     = 100
      batch_window   = 10
      trigger_type   = "EVENT"
      schedule       = null
      reporting_date = null
    },
    "change_request" = {
      name          = "uk-snowfall-change-request"
      description   = "Workflow for the change-request data"
      dataset       = "change_request"
      group         = "preparation"
      trigger_name   = "uk-snowfall-change-request-trigger"
      max_concurrent = 1
      batch_size     = 100
      batch_window   = 10
      trigger_type   = "EVENT"
      schedule       = null
      reporting_date = null
    },
    "incident_daily" = {
      name            = "uk-snowfall-incident-daily"
      description     = "Workflow for the incident-daily data"
      dataset         = "incident_daily"
      group           = "preparation"
      trigger_name    = "uk-snowfall-incident-daily-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "incident_intraday" = {
      name            = "uk-snowfall-incident-intraday"
      description     = "Workflow for the incident-intraday data"
      dataset         = "incident_intraday"
      group           = "preparation"
      trigger_name    = "uk-snowfall-incident-intraday-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "location" = {
      name            = "uk-snowfall-location"
      description     = "Workflow for the location data"
      dataset         = "location"
      group           = "preparation"
      trigger_name    = "uk-snowfall-location-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "location_hierarchy" = {
      name            = "uk-snowfall-location-hierarchy"
      description     = "Workflow for the location-hierarchy data"
      dataset         = "location_hierarchy"
      group           = "preparation"
      trigger_name    = "uk-snowfall-location-hierarchy-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "problem_record" = {
      name            = "uk-snowfall-problem-record"
      description     = "Workflow for the problem-record data"
      dataset         = "problem_record"
      group           = "preparation"
      trigger_name    = "uk-snowfall-problem-record-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "semantic_amazon_connect" = {
      name            = "uk-snowfall-semantic-amazon-connect"
      description     = "Semantic flow for the amazon connect"
      dataset         = "amazon_connect"
      group           = "semantic"
      trigger_name    = "uk-snowfall-semantic-amazon-connect-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 3 * * ? *)"
      reporting_date  = ""
    },
    "semantic_franchisee_incidents" = {
      name            = "uk-snowfall-semantic-franchisee-incidents"
      description     = "Semantic flow for the franchisee incidents"
      dataset         = "franchisee_incidents"
      group           = "semantic"
      trigger_name    = "uk-snowfall-semantic-franchisee-incidents-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 3 * * ? *)"
      reporting_date  = ""
    },
    "semantic_incidents_daily" = {
      name            = "uk-snowfall-semantic-incidents-daily"
      description     = "Semantic flow for the incidents daily"
      dataset         = "daily_incidents"
      group           = "semantic"
      trigger_name    = "uk-snowfall-semantic-incidents-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 3 * * ? *)"
      reporting_date  = ""
    },
    "service_offering" = {
      name            = "uk-snowfall-service-offering"
      description     = "Workflow for the Service Offering data"
      dataset         = "service_offering"
      group           = "preparation"
      trigger_name    = "uk-snowfall-service-offering-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "service_request" = {
      name            = "uk-snowfall-service-request"
      description     = "Workflow for the Service Request data"
      dataset         = "service_request"
      group           = "preparation"
      trigger_name    = "uk-snowfall-service-request-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "sys_user" = {
      name            = "uk-snowfall-sys-user"
      description     = "Workflow for the Sys User data"
      dataset         = "sys_user"
      group           = "preparation"
      trigger_name    = "uk-snowfall-sys-user-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "sys_user_group" = {
      name            = "uk-snowfall-sys-user-group"
      description     = "Workflow for the sys_user_group data"
      dataset         = "sys_user_group"
      group           = "preparation"
      trigger_name    = "uk-snowfall-sys-user-group-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "trading_hours" = {
      name            = "uk-snowfall-trading-hours"
      description     = "Workflow for the trading hours data"
      dataset         = "trading_hours"
      group           = "preparation"
      trigger_name    = "uk-snowfall-trading-hours-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "meraki" = {
      name            = "uk-snowfall-meraki"
      description     = "Workflow for the Meraki data"
      dataset         = "meraki"
      group           = "preparation"
      trigger_name    = "uk-snowfall-meraki-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "device_info" = {
      name            = "uk-snowfall-newrelic-rmp-device"
      description     = "Workflow for the newrelic rmp device data"
      dataset         = "newrelic_rmp_device_info"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-rmp-device-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "metrics_info" = {
      name            = "uk-snowfall-newrelic-rmp-metric"
      description     = "Workflow for the newrelic rmp metric data"
      dataset         = "newrelic_rmp_device_metrics"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-rmp-metric-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
  }
}


# Create AWS Glue Workflows dynamically from local values
resource "aws_glue_workflow" "glue_workflows" {
  for_each = local.workflows

  name                = each.value.name
  description         = each.value.description
  max_concurrent_runs = each.value.max_concurrent
  tags                = var.resource_tags

  default_run_properties = merge({
    "DATASET" = each.value.dataset
    "GROUP"   = each.value.group
  }, each.value.reporting_date != null ? { REPORTING_DATE = each.value.reporting_date } : {})

  lifecycle {
    prevent_destroy = true   # Prevent the workflow from being destroyed
    ignore_changes = [name, description]  # Ignore changes to these attributes
  }
}

# Create AWS Glue Triggers dynamically
resource "aws_glue_trigger" "glue_triggers" {
  for_each = local.workflows

  name          = each.value.trigger_name
  type          = each.value.trigger_type
  enabled       = true
  workflow_name = aws_glue_workflow.glue_workflows[each.key].name

  schedule = each.value.trigger_type == "SCHEDULED" ? each.value.schedule : null

  actions {
    job_name = var.glue_job_name
  }

  # Only include event batching if the trigger is event-based (not scheduled)
  dynamic "event_batching_condition" {
    for_each = each.value.trigger_type == "EVENT" ? [1] : []
    content {
      batch_size   = each.value.batch_size
      batch_window = each.value.batch_window
    }
  }

  lifecycle {
    prevent_destroy = true  # Prevent the trigger from being destroyed
    ignore_changes = [name, description]  # Ignore changes to these attributes
  }
}
