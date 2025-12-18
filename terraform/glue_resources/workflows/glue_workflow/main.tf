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
    "meraki_device_info" = {
      name            = "uk-snowfall-meraki-device-info"
      description     = "Workflow for the Meraki device info data"
      dataset         = "meraki_device_info"
      group           = "preparation"
      trigger_name    = "uk-snowfall-meraki-device-info-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "meraki_client_info" = {
      name            = "uk-snowfall-meraki-client-info"
      description     = "Workflow for the Meraki client info data"
      dataset         = "meraki_client_info"
      group           = "preparation"
      trigger_name    = "uk-snowfall-meraki-client-info-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "newrelic_rmp_device_info" = {
      name            = "uk-snowfall-newrelic-rmp-device_info"
      description     = "Workflow for the newrelic rmp device data"
      dataset         = "newrelic_rmp_device_info"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-rmp-device-info-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "newrelic_rmp_device_metrics" = {
      name            = "uk-snowfall-newrelic-rmp-device_metrics"
      description     = "Workflow for the newrelic rmp device metrics data"
      dataset         = "newrelic_rmp_device_metrics"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-rmp-device-metrics-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0/15 1-23 * * ? *)"
      reporting_date  = ""
    },
    "newrelic_rmp_network_info" = {
      name           = "uk-snowfall-newrelic-rmp-network-info"
      description    = "Workflow for the newrelic rmp network info data"
      dataset        = "newrelic_rmp_network_info"
      group          = "preparation"
      trigger_name   = "uk-snowfall-newrelic-rmp-network-info-trigger"
      max_concurrent = 1
      batch_size     = 100
      batch_window   = 10
      trigger_type   = "SCHEDULED"
      schedule       = "cron(0/15 1-23 * * ? *)"
      reporting_date = ""
    },
    "newrelic_rmp_process_info" = {
      name            = "uk-snowfall-newrelic-rmp-process_info"
      description     = "Workflow for the newrelic rmp process info data"
      dataset         = "newrelic_rmp_process_info"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-rmp-process-info-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0/15 1-23 * * ? *)"
      reporting_date  = ""
    },
    "newrelic_rmp_network_info_daily" = {
      name           = "uk-snowfall-newrelic-rmp-network-info-daily"
      description    = "Workflow for the New Relic RMP daily aggregated network info data"
      dataset        = "newrelic_rmp_network_info_daily"
      group          = "semantic"
      trigger_name   = "uk-snowfall-newrelic-rmp-network-info-daily-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 0 * * ? *)"
      reporting_date  = ""
    },
    "newrelic_rmp_device_metrics_daily" = {
      name            = "uk-snowfall-newrelic-rmp-device_metrics-daily"
      description     = "Workflow for the newrelic rmp device metrics data, triggered daily at 12 AM UTC"
      dataset         = "newrelic_rmp_device_metrics_daily"
      group           = "semantic"
      trigger_name    = "uk-snowfall-newrelic-rmp-device-metrics-daily-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 0 * * ? *)"
      reporting_date  = ""
    },
    "newrelic_digital_gma_foe_response" = {
      name            = "uk-snowfall-newrelic-digital-gma-foe-response"
      description     = "Workflow for the New Relic Digital GMA FOE Response data"
      dataset         = "newrelic_digital_gma_foe_response"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-digital-gma-foe-response-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "newrelic_digital_3po_foe_response" = {
      name            = "uk-snowfall-newrelic-digital-3po-foe-response"
      description     = "Workflow for the New Relic Digital 3PO FOE Response data"
      dataset         = "newrelic_digital_3po_foe_response"
      group           = "preparation"
      trigger_name    = "uk-snowfall-newrelic-digital-3po-foe-response-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "EVENT"
      schedule        = null
      reporting_date  = null
    },
    "ncr_service_now_service_case" = {
      name            = "uk-snowfall-ncr-service-now-service-case"
      description     = "Workflow for the newrelic rmp device metrics data"
      dataset         = "ncr_service_now_service_case"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-service-case-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_problem_record" = {
      name            = "uk-snowfall-ncr-service-now-problem-record"
      description     = "Workflow for the NCR ServiceNow Problem Record data"
      dataset         = "ncr_service_now_problem_record"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-problem-record-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_change_request" = {
      name            = "uk-snowfall-ncr-service-now-change-request"
      description     = "Workflow for the NCR ServiceNow Change Request data"
      dataset         = "ncr_service_now_change_request"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-change-request-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_incident" = {
      name            = "uk-snowfall-ncr-service-now-incident"
      description     = "Workflow for the NCR ServiceNow Incident data"
      dataset         = "ncr_service_now_incident"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-incident-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_incident_task" = {
      name            = "uk-snowfall-ncr-service-now-incident-task"
      description     = "Workflow for the NCR ServiceNow Incident Task data"
      dataset         = "ncr_service_now_incident_task"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-incident-task-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)" # offset to avoid overlap with incident
      reporting_date  = ""
    },
    "ncr_service_now_knowledge_base" = {
      name            = "uk-snowfall-ncr-service-now-knowledge-base"
      description     = "Workflow for the NCR ServiceNow Knowledge Base data"
      dataset         = "ncr_service_now_knowledge_base"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-knowledge-base-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_knowledge" = {
      name            = "uk-snowfall-ncr-service-now-knowledge"
      description     = "Workflow for the NCR ServiceNow Knowledge Base data"
      dataset         = "ncr_service_now_knowledge"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-knowledge-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "ncr_service_now_worknotes" = {
      name            = "uk-snowfall-ncr-service-now-worknotes"
      description     = "Workflow for the NCR ServiceNow Worknotes data"
      dataset         = "ncr_service_now_worknotes"
      group           = "preparation"
      trigger_name    = "uk-snowfall-ncr-service-now-worknotes-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)" # offset to avoid overlap with incident & task
      reporting_date  = ""
    },
    "happysignals" = {
      name            = "uk-snowfall-happysignals"
      description     = "Workflow for the HappySignals data"
      dataset         = "happysignals"
      group           = "preparation"
      trigger_name    = "uk-snowfall-happysignals-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 1
      trigger_type    = "SCHEDULED"
      schedule        = "cron(45 * * * ? *)"
      reporting_date  = ""
    },
    "service_agent_server_files" = {
      name            = "uk-snowfall-service-agent-server-files"
      description     = "Workflow for the newrelic rmp device data"
      dataset         = "service_agent_main_job"
      group           = "processed"
      trigger_name    = "uk-snowfall-service-agent-server-files-trigger"
      max_concurrent  = 1
      batch_size      = 100
      batch_window    = 10
      trigger_type    = "SCHEDULED"
      schedule        = "cron(30 * * * ? *)"
      reporting_date  = ""
    },
    "genesys_contact_settings" = {
      "name" = "uk-snowfall-genesys-contact-settings"
      "description" = "Workflow for Genesys Contact Center Settings data"
      "dataset" = "genesys_contact_settings"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-contact-settings-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_conv_attributes" = {
      "name" = "uk-snowfall-genesys-conv-attributes"
      "description" = "Workflow for Genesys Conversation Attributes data"
      "dataset" = "genesys_conv_attributes"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-conv-attributes-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_conversations_det" = {
      "name" = "uk-snowfall-genesys-conversations-detail"
      "description" = "Workflow for Genesys Conversations Detail data"
      "dataset" = "genesys_conversations_det"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-conversations-detail-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_conversations" = {
      "name" = "uk-snowfall-genesys-conversations"
      "description" = "Workflow for Genesys Conversations data"
      "dataset" = "genesys_conversations"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-conversations-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_presence" = {
      "name" = "uk-snowfall-genesys-presence"
      "description" = "Workflow for Genesys Primary Presence data"
      "dataset" = "genesys_presence"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-presence-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_queue_abandons" = {
      "name" = "uk-snowfall-genesys-queue-abandons"
      "description" = "Workflow for Genesys Queue Abandons data"
      "dataset" = "genesys_queue_abandons"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-queue-abandons-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_queue_config" = {
      "name" = "uk-snowfall-genesys-queue-config"
      "description" = "Workflow for Genesys Queue Configuration data"
      "dataset" = "genesys_queue_config"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-queue-config-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_routing_status" = {
      "name" = "uk-snowfall-genesys-routing-status"
      "description" = "Workflow for Genesys Routing Status data"
      "dataset" = "genesys_routing_status"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-routing-status-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_queue_history" = {
      "name" = "uk-snowfall-genesys-queue-history"
      "description" = "Workflow for Genesys Queue Interval History data"
      "dataset" = "genesys_queue_history"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-queue-history-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_session_summary" = {
      "name" = "uk-snowfall-genesys-session-summary"
      "description" = "Workflow for Genesys Session Summary data"
      "dataset" = "genesys_session_summary"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-session-summary-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = "cron(45 * * * ? *)"
      "reporting_date" = ""
    },
    "genesys_user_details" = {
      "name" = "uk-snowfall-genesys-user-details"
      "description" = "Workflow for Genesys User Details data"
      "dataset" = "genesys_user_details"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-user-details-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "genesys_user_status_history" = {
      "name" = "uk-snowfall-genesys-user-status-history"
      "description" = "Workflow for Genesys User Status Interval History data"
      "dataset" = "genesys_user_status_history"
      "group" = "preparation"
      "trigger_name" = "uk-snowfall-genesys-user-status-history-trigger"
      "max_concurrent" = 1
      "batch_size" = 100
      "batch_window" = 1
      "trigger_type" = "SCHEDULED"
      "schedule" = null
      "reporting_date" = ""
    },
    "restaurant_count_by_day" = {
      name            = "uk-snowfall-restaurant-count-by-day"
      description     = "Workflow for the restaurant count by day data, triggered daily at 1 AM UTC"
      dataset         = "restaurant_count_by_day"
      group           = "processed"
      trigger_name    = "uk-snowfall-restaurant-count-by-day-trigger"
      max_concurrent  = 1
      batch_size      = null
      batch_window    = null
      trigger_type    = "SCHEDULED"
      schedule        = "cron(0 1 * * ? *)"
      reporting_date  = ""
    }
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
    prevent_destroy = false   # Prevent the workflow from being destroyed
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
    prevent_destroy = false   # Prevent the trigger from being destroyed
    ignore_changes = [name, description]  # Ignore changes to these attributes
  }
}
