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
    ncr_change_request      = "ncr_service_now/UK-SNowFall-ServiceNow-ChangeRequest/"
    ncr_incident_daily      = "ncr_service_now/UK-SNowFall-ServiceNow-Incident-Daily/"
    ncr_incident_intraday   = "ncr_service_now/UK-SNowFall-ServiceNow-Incident-Intraday/"
    ncr_location            = "ncr_service_now/UK-SNowFall-ServiceNow-Location/"
    ncr_problem_record      = "ncr_service_now/UK-SNowFall-ServiceNow-ProblemRecord/"
    ncr_service_offering    = "ncr_service_now/UK-SNowFall-ServiceNow-ServiceOffering/"
    ncr_service_request     = "ncr_service_now/UK-SNowFall-ServiceNow-ServiceRequest/"
    ncr_sys_user            = "ncr_service_now/UK-SNowFall-ServiceNow-SysUser/"
    ncr_sys_user_group      = "ncr_service_now/UK-SNowFall-ServiceNow-Sys-User-Group/"
    ncr_case                = "ncr_service_now/UK-SNowFall-ServiceNow-Case/"
    ncr_incident_task ="ncr_service_now/UK-SNowFall-ServiceNow-Incident-Task/"
  }
}

  


# Updated to use Landing Sync Lambda
resource "aws_s3_bucket_notification" "datashare_landing_trigger_notification" {
  bucket = aws_s3_bucket.datashare_landing_bucket.id

  lambda_function {
    lambda_function_arn = var.datashare_landing_trigger_arn
    events              = ["s3:ObjectCreated:*"]
    id                  = "moving the file to original landing bucket "
  }
  depends_on = [ aws_s3_bucket.datashare_landing_bucket, var.datashare_landing_trigger_arn, var.allow_landing_trigger]
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
    newrelic_rmp_device       = "newrelic/newrelic_rmp_device/"
    newrelic_rmp_device_metrics      = "newrelic/newrelic_rmp_device_metrics/"
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

# Updated to use Processed Trigger Lambda (Datashare NCR Webhook)
resource "aws_s3_bucket_notification" "datashare_processed_trigger_notification" {
  bucket = aws_s3_bucket.datashare_processed_bucket.id

  lambda_function {
    lambda_function_arn = var.datashare_ncr_webhook_arn
    events              = ["s3:ObjectCreated:*"]
    id                  = "trigger ncr webhook  "
  }
  depends_on = [
    aws_s3_bucket.datashare_processed_bucket,
    var.datashare_ncr_webhook_arn,
    var.allow_ncr_webhook
  ]
}

