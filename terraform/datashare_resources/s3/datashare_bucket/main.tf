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

# resource "aws_s3_bucket_policy" "datashare_landing_bucket_policy" {
#   bucket = aws_s3_bucket.datashare_landing_bucket.id
#   policy = data.template_file.datashare_bucket_policy.rendered
# }

# data "template_file" "datashare_bucket_policy" {
#   template = file("${path.module}/bucket_policy/policy.json")

#   vars = {
#     environment    = var.environment
#     account_number = var.account_number
#   }
# }

# Creating folders in Datashare Landing Bucket with "datasharing_service_now" prefix
resource "aws_s3_object" "datashare_landing_folder" {
  bucket                  = aws_s3_bucket.datashare_landing_bucket.id
  acl                     = "private"
  key                     = each.value
  source                  = "/dev/null"
  server_side_encryption  = "aws:kms"
  for_each = {
    ncr_change_request      = "ncr_service_now/change_request/"
    ncr_incident_daily      = "ncr_service_now/incident/daily/"
    ncr_incident_intraday   = "ncr_service_now/incident/intraday/"
    ncr_problem_record      = "ncr_service_now/problem_record/"
    ncr_service_now_case    = "ncr_service_now/service_case/"
    ncr_incident_task       = "ncr_service_now/incident_task/"
    ncr_knowledge_base      = "ncr_service_now/knowledge_base/"
    ncr_knowledge      = "ncr_service_now/knowledge/"
    ncr_knowledge_feedback      = "ncr_service_now/knowledge_feedback/"
    ncr_knowledge_use      = "ncr_service_now/knowledge_use/"
    genesys                 = "genesys/"
    google_contact_center   = "gcc/"
    happysignals            = "happysignals/"
    error= "error/nonparquet"

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
    amazon_connect            = "amazon_connect/"
    location_trading_hrs      = "ods/trading_hours/"
    location_hierarchy        = "ods/location_hierarchy/"
    location_adj_trading_hrs  = "ods/adj_trading_hours/"
    cisco_meraki              = "meraki/"
    newrelic                  = "newrelic/"
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

