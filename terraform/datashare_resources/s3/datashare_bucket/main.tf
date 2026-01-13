# ####### Creation of Datashare Landing Bucket ################
resource "aws_s3_bucket" "datashare_landing_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-datashare-landing-${var.account_number}"
  tags   = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "datashare_landing_versioning" {
  bucket = aws_s3_bucket.datashare_landing_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datashare_landing_lifecycle_rules" {
  depends_on = [aws_s3_bucket_versioning.datashare_landing_versioning]
  bucket = aws_s3_bucket.datashare_landing_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}



# Creating folders in Datashare Landing Bucket with "datasharing_service_now" prefix
resource "aws_s3_object" "datashare_landing_folder" {
  bucket                  = aws_s3_bucket.datashare_landing_bucket.id
  acl                     = "private"
  key                     = each.value
  source                  = "/dev/null"
  server_side_encryption  = "aws:kms"
  for_each = {
    ncr_change_request        = "ncr_service_now/change_request/"
    ncr_incident              = "ncr_service_now/incident/"
    ncr_problem_record        = "ncr_service_now/problem_record/"
    ncr_service_now_case      = "ncr_service_now/service_case/"
    ncr_incident_task         = "ncr_service_now/incident_task/"
    ncr_knowledge_base        = "ncr_service_now/knowledge_base/"
    ncr_knowledge             = "ncr_service_now/knowledge/"
    ncr_knowledge_feedback    = "ncr_service_now/knowledge_feedback/"
    ncr_knowledge_use         = "ncr_service_now/knowledge_use/"
    ncr_case_worknotes        = "ncr_service_now/worknotes/"
    ncr_incident_sla          = "ncr_service_now/incident_sla/"
    ncr_account               = "ncr_service_now/account/"
    ncr_problem_task          = "ncr_service_now/problem_task/"
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
    error= "error/nonparquet/"
    test= "test/"
  }
   lifecycle {    
    ignore_changes = [      
      etag,
      version_id,
      source_hash
    ]  
  }
}

  





# ####### Creation of Datashare Processed Bucket ################
resource "aws_s3_bucket" "datashare_processed_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall-datashare-processed-${var.account_number}"
  tags   = var.resource_tags
  force_destroy = true
}

# Creating folders in Datashare Processed Bucket with the required paths
resource "aws_s3_object" "datashare_processed_folders" {
  bucket                  = aws_s3_bucket.datashare_processed_bucket.id
  acl                     = "private"
  key                     = each.value
  source                  = "/dev/null"
  server_side_encryption  = "aws:kms"
  for_each = {
    location_trading_hrs      = "ods/trading_hours/"
    location_hierarchy        = "ods/location_hierarchy/"
    location_adj_trading_hrs  = "ods/adj_trading_hours/"
    cisco_meraki              = "meraki/"
    newrelic                  = "newrelic/"
    ods_user_data             = "ods_user_data/"
  }
  lifecycle {    
    ignore_changes = [      
      etag,
      version_id,
      source_hash
    ]  
  }
}


resource "aws_s3_bucket_versioning" "datashare_processed_versioning" {
  bucket = aws_s3_bucket.datashare_processed_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datashare_processed_lifecycle_rules" {
  depends_on = [aws_s3_bucket_versioning.datashare_processed_versioning]
  bucket = aws_s3_bucket.datashare_processed_bucket.id
  rule {
    id = "Removing objects with delete markers after 30 days"
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    status = "Enabled"
  }
}

# ########## Datashare Tech360 Bucket ##########
resource "aws_s3_bucket" "datashare_tech360_bucket" {
  bucket        = "eu-central1-${var.environment}-uk-snowfall-datashare-tech360-${var.account_number}"
  force_destroy = true
  tags          = var.resource_tags
}

# ########## Bucket Versioning ##########
resource "aws_s3_bucket_versioning" "datashare_tech360_versioning" {
  bucket = aws_s3_bucket.datashare_tech360_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ########## Lifecycle Rule ##########
resource "aws_s3_bucket_lifecycle_configuration" "datashare_tech360_lifecycle" {
  depends_on = [aws_s3_bucket_versioning.datashare_tech360_versioning]
  bucket     = aws_s3_bucket.datashare_tech360_bucket.id

  rule {
    id     = "Expire noncurrent versions after 30 days"
    status = "Enabled"
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# ########## Bucket-Wide Encryption Enforcement (Default KMS Key) ##########
resource "aws_s3_bucket_server_side_encryption_configuration" "tech360_encryption" {
  bucket = aws_s3_bucket.datashare_tech360_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# ########## NCR Folder Creation ##########
resource "aws_s3_object" "datashare_tech360_ncr_folders" {
  for_each = {
    incident             = "ncr_service_now/incident/"
    test = "ncr_service_now/test/"
    # problem_record       = "ncr_service_now/problem_record/"
    # service_now_case     = "ncr_service_now/service_case/"
    # incident_task        = "ncr_service_now/incident_task/"
  }

  bucket                 = aws_s3_bucket.datashare_tech360_bucket.id
  key                    = each.value
  source                 = "/dev/null"
  acl                    = "private"
  server_side_encryption = "aws:kms"

  lifecycle {
    prevent_destroy = false
    ignore_changes  = [
      source,
      etag,
      version_id,
      source_hash
    ]
  }
}
