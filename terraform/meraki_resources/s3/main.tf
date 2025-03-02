# ####### Creation of Raw Bucket ################
resource "aws_s3_bucket" "raw_bucket" {
  bucket = "eu-central1-${var.environment}-uk-snowfall2-raw-${var.account_number}"
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
      meraki = "meraki/"
    }
}

resource "aws_s3_bucket_notification" "enabling_event_bridge_notification" {
  bucket = aws_s3_bucket.raw_bucket.bucket
  eventbridge = true
}
