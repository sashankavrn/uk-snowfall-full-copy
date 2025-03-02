# ####### Creation of Raw Bucket ################
resource "aws_s3_bucket" "raw_bucket" {
  bucket        = "eu-central1-${var.environment}-uk-snowfall2-raw-${var.account_number}"
  tags          = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "raw_versioning" {
  bucket = aws_s3_bucket.raw_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "raw_folder" {
  bucket                 = aws_s3_bucket.raw_bucket.id
  acl                    = "private"
  key                    = "meraki/"
  source                 = "/dev/null"
  server_side_encryption = "aws:kms"
}

resource "aws_s3_bucket_notification" "raw_bucket_notification" {
  bucket     = aws_s3_bucket.raw_bucket.id
  eventbridge = true
}

# ####### Creation of Landing Bucket ################
resource "aws_s3_bucket" "landing_bucket" {
  bucket        = "eu-central1-${var.environment}-uk-snowfall2-landing-${var.account_number}"
  tags          = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "landing_versioning" {
  bucket = aws_s3_bucket.landing_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "landing_folder" {
  bucket                 = aws_s3_bucket.landing_bucket.id
  acl                    = "private"
  key                    = "meraki/"
  source                 = "/dev/null"
  server_side_encryption = "aws:kms"
}

resource "aws_s3_bucket_notification" "landing_bucket_notification" {
  bucket     = aws_s3_bucket.landing_bucket.id
  eventbridge = true
}

# ####### Creation of Processed Bucket ################
resource "aws_s3_bucket" "processed_bucket" {
  bucket        = "eu-central1-${var.environment}-uk-snowfall2-processed-${var.account_number}"
  tags          = var.resource_tags
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "processed_versioning" {
  bucket = aws_s3_bucket.processed_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "processed_folder" {
  bucket                 = aws_s3_bucket.processed_bucket.id
  acl                    = "private"
  key                    = "meraki/"
  source                 = "/dev/null"
  server_side_encryption = "aws:kms"
}

resource "aws_s3_bucket_notification" "processed_bucket_notification" {
  bucket     = aws_s3_bucket.processed_bucket.id
  eventbridge = true
}
