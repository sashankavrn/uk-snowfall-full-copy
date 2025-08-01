####### Creation of Landing Bucket ################

resource "aws_s3_bucket" "landing_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "landing_versioning" {
  bucket = aws_s3_bucket.landing_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "landing_lifecycle_rules" {
  depends_on = [ aws_s3_bucket_versioning.landing_versioning]
  bucket = aws_s3_bucket.landing_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}


resource "aws_s3_bucket_policy" "allow_access_from_appflow_and_connect" {
  bucket = aws_s3_bucket.landing_bucket.id
  policy = data.template_file.bucket_policy.rendered
  lifecycle {
    ignore_changes = [
      policy
    ]
  }

}

data "template_file" "bucket_policy" {
  template = file("${path.module}/bucket_policy/policy.json")

  vars = {
    environment = var.environment
    account_number = var.account_number
  }
}

resource "aws_s3_object" "landing_folder" {
    bucket 					= "${aws_s3_bucket.landing_bucket.id}"
    acl    					= "private"
    key    					= each.value
    source 					= "/dev/null"
    server_side_encryption 	= "aws:kms"
    for_each = {
      amazon_connect      = "connect/"
      change_request      = "service_now/UK-SNowFall-ServiceNow-ChangeRequest/"
      incident_daily      = "service_now/UK-SNowFall-ServiceNow-Incident-Daily/"
      incident_intraday   = "service_now/UK-SNowFall-ServiceNow-Incident-Intraday/"
      location            = "service_now/UK-SNowFall-ServiceNow-Location/"
      problem_record      = "service_now/UK-SNowFall-ServiceNow-ProblemRecord/"
      service_offering    = "service_now/UK-SNowFall-ServiceNow-ServiceOffering/"
      service_request     = "service_now/UK-SNowFall-ServiceNow-ServiceRequest/"
      sys_user            = "service_now/UK-SNowFall-ServiceNow-SysUser/"
      sys_user_group      = "service_now/UK-SNowFall-ServiceNow-Sys-User-Group/"
      ods                 = "ods/"
      restaurant_config   = "restaurant_config/"
      cisco_meraki        = "meraki/"
      cisco_meraki_client_info       = "meraki/client_info/"
      cisco_meraki_device_info       = "meraki/device_info/"
      newrelic_rmp_device = "newrelic/newrelic_rmp_device_info/"
      newrelic_rmp_device_metrics      = "newrelic/newrelic_rmp_device_metrics/"
      newrelic_rmp_process_info = "newrelic/newrelic_rmp_process_info/"
      newrelic_digital_gma_foe_response = "newrelic/newrelic_digital_gma_foe_response/"
      newrelic_digital_3po_foe_response= "newrelic/newrelic_digital_3po_foe_response/"
      ncr_change_request      = "ncr_service_now/change_request/"
      ncr_incident     = "ncr_service_now/incident/"
      ncr_problem_record      = "ncr_service_now/problem_record/"
      ncr_service_now_case    = "ncr_service_now/service_case/"
      ncr_incident_task       = "ncr_service_now/incident_task/"
      ncr_knowledge_base      = "ncr_service_now/knowledge_base/"
      ncr_knowledge      = "ncr_service_now/knowledge/"
      ncr_knowledge_feedback      = "ncr_service_now/knowledge_feedback/"
      ncr_knowledge_use      = "ncr_service_now/knowledge_use/"
      genesys_contact_settings  = "genesys/contact_center_settings/"
      genesys_conv_attributes   = "genesys/conversation_attributes/"
      genesys_conversations_det = "genesys/conversations_detail/"
      genesys_conversations     = "genesys/conversations/"
      genesys_presence          = "genesys/primary_presence/"
      genesys_queue_abandons    = "genesys/queue_abandons/"
      genesys_queue_config      = "genesys/queue_configuration/"
      genesys_routing_status    = "genesys/routing_status/"
      genesys_queue_history     = "genesys/queue_interval_history/"
      genesys_session_summary   = "genesys/session_summary/"
      genesys_user_details      = "genesys/user_details/"
      genesys_user_status_history = "genesys/user_status_interval_history/"
      google_contact_center   = "gcc/"
      happysignals            = "happysignals/"
      ncr_service_now_case_worknotes = "ncr_service_now/case_worknotes/"
    }
}


resource "aws_s3_bucket_notification" "landing_trigger_notification" {
  bucket = aws_s3_bucket.landing_bucket.id

  lambda_function {
    lambda_function_arn = var.lambda_landing_func_arn
    events              = ["s3:ObjectCreated:*"]
    id = "Moving files to Raw Bucket"
  }
  depends_on = [ aws_s3_bucket.landing_bucket,var.lambda_landing_func_arn,var.lambda_permission]
}


# ####### Creation of Raw Bucket ################
resource "aws_s3_bucket" "raw_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "raw_versioning" {
  bucket = aws_s3_bucket.raw_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "raw_folder" {
    bucket 					= "${aws_s3_bucket.raw_bucket.id}"
    acl    					= "private"
    key    					= each.value
    source 					= "/dev/null"
    server_side_encryption 	= "aws:kms"
    for_each = {
      archive                   = "archive/"
      amazon_connect            = "amazon_connect/"
      change_request            = "service_now/change_request/"
      incident_intraday         = "service_now/incident/intraday/"
      incident_daily            = "service_now/incident/daily/"
      location                  = "service_now/location/"
      problem_record            = "service_now/problem_record/"
      service_request           = "service_now/service_request/"
      service_offering          = "service_now/service_offering/"
      sys_user_group            = "service_now/sys_user_group/"
      sys_user                  = "service_now/sys_user/"
      location_trading_hrs      = "ods/trading_hours/"
      location_hierarchy        = "ods/location_hierarchy/"
      location_adj_trading_hrs  = "ods/adj_trading_hours/"
      ods_user_data             = "ods/user_data/"
      restaurant_config         = "restaurant_config/"
      cisco_meraki              = "meraki/"
      cisco_meraki_client_info       = "meraki/client_info/"
      cisco_meraki_device_info       = "meraki/device_info/"
      newrelic_rmp_device = "newrelic/newrelic_rmp_device_info/"
      newrelic_rmp_device_metrics      = "newrelic/newrelic_rmp_device_metrics/"
      newrelic_rmp_process_info = "newrelic/newrelic_rmp_process_info/"
      newrelic_digital_gma_foe_response = "newrelic/newrelic_digital_gma_foe_response/"
      newrelic_digital_3po_foe_response= "newrelic/newrelic_digital_3po_foe_response/"
      ncr_change_request      = "ncr_service_now/change_request/"
      ncr_incident     = "ncr_service_now/incident/"
      ncr_problem_record      = "ncr_service_now/problem_record/"
      ncr_service_now_case    = "ncr_service_now/service_case/"
      ncr_incident_task       = "ncr_service_now/incident_task/"
      ncr_knowledge_base      = "ncr_service_now/knowledge_base/"
      ncr_knowledge      = "ncr_service_now/knowledge/"
      ncr_knowledge_feedback      = "ncr_service_now/knowledge_feedback/"
      ncr_knowledge_use      = "ncr_service_now/knowledge_use/"
      genesys_contact_settings  = "genesys/contact_center_settings/"
      genesys_conv_attributes   = "genesys/conversation_attributes/"
      genesys_conversations_det = "genesys/conversations_detail/"
      genesys_conversations     = "genesys/conversations/"
      genesys_presence          = "genesys/primary_presence/"
      genesys_queue_abandons    = "genesys/queue_abandons/"
      genesys_queue_config      = "genesys/queue_configuration/"
      genesys_routing_status    = "genesys/routing_status/"
      genesys_queue_history     = "genesys/queue_interval_history/"
      genesys_session_summary   = "genesys/session_summary/"
      genesys_user_details      = "genesys/user_details/"
      genesys_user_status_history = "genesys/user_status_interval_history/"
      google_contact_center   = "gcc/"
      happysignals            = "happysignals/"
      service_agent_server_files = "service_agent_server_files/uploads/"
       ncr_service_now_case_worknotes = "ncr_service_now/case_worknotes/"
    }
}

resource "aws_s3_bucket_notification" "enabling_event_bridge_notification" {
  bucket = aws_s3_bucket.raw_bucket.bucket
  eventbridge = true
}


# ####### Creation of Preparation Bucket ################
resource "aws_s3_bucket" "preparation_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-preparation-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "preparation_versioning" {
  bucket = aws_s3_bucket.preparation_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "preparation_lifecycle_rules" {
  depends_on = [aws_s3_bucket_versioning.preparation_versioning]
    bucket = aws_s3_bucket.preparation_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}

resource "aws_s3_object" "preparation_folder" {
    bucket 					= "${aws_s3_bucket.preparation_bucket.id}"
    acl    					= "private"
    key    					= each.value
    source 					= "/dev/null"
    server_side_encryption 	= "aws:kms"
    for_each = {
      amazon_connect            = "amazon_connect/"
      change_request            = "service_now/change_request/"
      incident_intraday         = "service_now/incident/intraday/"
      incident_daily            = "service_now/incident/daily/"
      location                  = "service_now/location/"
      problem_record            = "service_now/problem_record/"
      service_request           = "service_now/service_request/"
      service_offering          = "service_now/service_offering/"
      sys_user_group            = "service_now/sys_user_group/"
      sys_user                  = "service_now/sys_user/"
      location_trading_hrs      = "ods/trading_hours/"
      location_hierarchy        = "ods/location_hierarchy/"
      location_adj_trading_hrs  = "ods/adj_trading_hours/"
      cisco_meraki              = "meraki/"
      cisco_meraki_client_info       = "meraki/client_info/"
      cisco_meraki_device_info       = "meraki/device_info/"
      newrelic_rmp_device = "newrelic/newrelic_rmp_device_info/"
      newrelic_rmp_device_metrics      = "newrelic/newrelic_rmp_device_metrics/"
      newrelic_rmp_process_info = "newrelic/newrelic_rmp_process_info/"
      newrelic_digital_gma_foe_response = "newrelic/newrelic_digital_gma_foe_response/"
      newrelic_digital_3po_foe_response= "newrelic/newrelic_digital_3po_foe_response/"
      ncr_change_request      = "ncr_service_now/change_request/"
      ncr_incident     = "ncr_service_now/incident/"
      ncr_problem_record      = "ncr_service_now/problem_record/"
      ncr_service_now_case    = "ncr_service_now/service_case/"
      ncr_incident_task       = "ncr_service_now/incident_task/"
      ncr_knowledge_base      = "ncr_service_now/knowledge_base/"
      ncr_knowledge      = "ncr_service_now/knowledge/"
      ncr_knowledge_feedback      = "ncr_service_now/knowledge_feedback/"
      ncr_knowledge_use      = "ncr_service_now/knowledge_use/"
      genesys_contact_settings  = "genesys/contact_center_settings/"
      genesys_conv_attributes   = "genesys/conversation_attributes/"
      genesys_conversations_det = "genesys/conversations_detail/"
      genesys_conversations     = "genesys/conversations/"
      genesys_presence          = "genesys/primary_presence/"
      genesys_queue_abandons    = "genesys/queue_abandons/"
      genesys_queue_config      = "genesys/queue_configuration/"
      genesys_routing_status    = "genesys/routing_status/"
      genesys_queue_history     = "genesys/queue_interval_history/"
      genesys_session_summary   = "genesys/session_summary/"
      genesys_user_details      = "genesys/user_details/"
      genesys_user_status_history = "genesys/user_status_interval_history/"
      google_contact_center   = "gcc/"
      happysignals            = "happysignals/"
      service_agent_server_files = "service_agent_server_files/uploads/"
      ncr_service_now_case_worknotes = "ncr_service_now/case_worknotes/"
    }
}

# ####### Creation of Artifact Bucket ################

resource "aws_s3_bucket" "artifact_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-artifact-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}


################### Uplaoding Scripts to S3 #######################

resource "aws_s3_object" "temporary_folder" {
  bucket = aws_s3_bucket.artifact_bucket.id
  key    = "temporary/" 
  source = "/dev/null" 
}

#####################################################################################

# ####### Creation of Processed Bucket ################
resource "aws_s3_bucket" "processed_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-processed-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "processed_versioning" {
  bucket = aws_s3_bucket.processed_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "processed_lifecycle_rules" {
  depends_on = [ aws_s3_bucket_versioning.processed_versioning]
  bucket = aws_s3_bucket.processed_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}

resource "aws_s3_object" "processed_folder" {
    bucket 					= "${aws_s3_bucket.processed_bucket.id}"
    acl    					= "private"
    key    					= each.value
    source 					= "/dev/null"
    server_side_encryption 	= "aws:kms"
    for_each = {
      amazon_connect            = "amazon_connect/"
      change_request            = "service_now/change_request/"
      incident_intraday         = "service_now/incident/intraday/"
      incident_daily            = "service_now/incident/daily/"
      location                  = "service_now/location/"
      problem_record            = "service_now/problem_record/"
      service_request           = "service_now/service_request/"
      service_offering          = "service_now/service_offering/"
      sys_user_group            = "service_now/sys_user_group/"
      sys_user                  = "service_now/sys_user/"
      location_trading_hrs      = "ods/trading_hours/"
      location_hierarchy        = "ods/location_hierarchy/"
      location_adj_trading_hrs  = "ods/adj_trading_hours/"
      cisco_meraki              = "meraki/"
      cisco_meraki_client_info       = "meraki/client_info/"
      cisco_meraki_device_info       = "meraki/device_info/"
      newrelic_rmp_device = "newrelic/newrelic_rmp_device_info/"
      newrelic_rmp_device_metrics      = "newrelic/newrelic_rmp_device_metrics/"
      newrelic_rmp_process_info = "newrelic/newrelic_rmp_process_info/"
      newrelic_digital_gma_foe_response = "newrelic/newrelic_digital_gma_foe_response/"
      newrelic_digital_3po_foe_response= "newrelic/newrelic_digital_3po_foe_response/"
      ncr_change_request      = "ncr_service_now/change_request/"
      ncr_incident     = "ncr_service_now/incident/"
      ncr_problem_record      = "ncr_service_now/problem_record/"
      ncr_service_now_case    = "ncr_service_now/service_case/"
      ncr_incident_task       = "ncr_service_now/incident_task/"
      ncr_knowledge_base      = "ncr_service_now/knowledge_base/"
      ncr_knowledge      = "ncr_service_now/knowledge/"
      ncr_knowledge_feedback      = "ncr_service_now/knowledge_feedback/"
      ncr_knowledge_use      = "ncr_service_now/knowledge_use/"
      genesys_contact_settings  = "genesys/contact_center_settings/"
      genesys_conv_attributes   = "genesys/conversation_attributes/"
      genesys_conversations_det = "genesys/conversations_detail/"
      genesys_conversations     = "genesys/conversations/"
      genesys_presence          = "genesys/primary_presence/"
      genesys_queue_abandons    = "genesys/queue_abandons/"
      genesys_queue_config      = "genesys/queue_configuration/"
      genesys_routing_status    = "genesys/routing_status/"
      genesys_queue_history     = "genesys/queue_interval_history/"
      genesys_session_summary   = "genesys/session_summary/"
      genesys_user_details      = "genesys/user_details/"
      genesys_user_status_history = "genesys/user_status_interval_history/"
      google_contact_center   = "gcc/"
      happysignals            = "happysignals/"
      service_agent_server_files = "service_agent_server_files/uploads/"
      ncr_service_now_case_worknotes = "ncr_service_now/case_worknotes/"
      ods_location_restaurant_count_by_day = "restaurant_count_by_day/"
    }
}


# ####### Creation of Semantic Bucket ################
resource "aws_s3_bucket" "semantic_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-semantic-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "semantic_versioning" {
  bucket = aws_s3_bucket.semantic_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "semantic_lifecycle_rules" {
  depends_on = [ aws_s3_bucket_versioning.semantic_versioning]
  bucket = aws_s3_bucket.semantic_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}

###### Creation of Athena Bucket ##############
resource "aws_s3_bucket" "athena_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-athena-${var.account_number}"
  tags   = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_lifecycle" {
  bucket = aws_s3_bucket.athena_bucket.id

  rule {
    id     = "Delete After 30 Days"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

# ####### Creation of Snowfall Service Agent Bucket ################
resource "aws_s3_bucket" "service_agent_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-service-agent-${var.account_number}"
  tags = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "service_agent_versioning" {
  bucket = aws_s3_bucket.service_agent_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "uploads_folder" {
  bucket                  = aws_s3_bucket.service_agent_bucket.id
  acl                     = "private"
  key                     = "uploads/"
  source                  = "/dev/null"
  server_side_encryption  = "aws:kms"
}


resource "aws_s3_object" "serverlist_folder" {
  bucket = aws_s3_bucket.service_agent_bucket.id
  acl= "private"
  key= "server_list/"
  source= "/dev/null"
  server_side_encryption= "aws:kms"
}


resource "aws_s3_bucket_notification" "service_agent_enabling_event_bridge_notification" {
  bucket = aws_s3_bucket.service_agent_bucket.bucket
  eventbridge = true
}

resource "aws_s3_bucket_lifecycle_configuration" "service_agent_lifecycle_rules" {
  depends_on = [aws_s3_bucket_versioning.service_agent_versioning]
  bucket = aws_s3_bucket.service_agent_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}

# ####### Creation of Snowfall Service Temp Bucket ################

resource "aws_s3_bucket" "temp_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-temp-${var.account_number}"
  tags   = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "temp_lifecycle_rules" {
  bucket = aws_s3_bucket.temp_bucket.id

  rule {
    id     = "Removing objects with delete markers after 30 days"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_object" "temp_folder" {
  bucket  = aws_s3_bucket.temp_bucket.id
  key     = "meraki/client_info/"
  content = ""
}
