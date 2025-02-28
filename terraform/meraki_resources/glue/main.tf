# IAM Role for Glue Crawler
resource "aws_iam_role" "glue_crawler_role" {
  name               = "GlueCrawlerRole-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
  tags               = var.resource_tags
}

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# IAM Policy for Glue Crawler
resource "aws_iam_policy" "glue_crawler_policy" {
  name        = "GlueCrawlerPolicy-${var.environment}"
  description = "IAM policy for Glue crawler to access S3 and Glue resources"
  policy      = data.aws_iam_policy_document.glue_permissions.json
}

data "aws_iam_policy_document" "glue_permissions" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetTables",
      "glue:UpdateTable",
      "glue:GetTable",
      "glue:CreateTable",
      "glue:BatchCreatePartition",
      "glue:UpdatePartition",
      "glue:GetPartition",
      "glue:BatchGetPartition"
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${var.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:database/${var.database_name}",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:table/${var.database_name}/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/aws-glue/*"]
  }
}

resource "aws_iam_role_policy_attachment" "glue_s3_access" {
  role       = aws_iam_role.glue_crawler_role.name
  policy_arn = aws_iam_policy.glue_crawler_policy.arn
}

# Create Glue Database
resource "aws_glue_catalog_database" "glue_database" {
  name = var.database_name
  description = "Glue database for storing metadata of Meraki data"
}

# Glue Crawler
resource "aws_glue_crawler" "glue_crawler" {
  name          = "meraki-glue-crawler-${var.environment}"
  database_name = aws_glue_catalog_database.glue_database.name
  role          = aws_iam_role.glue_crawler_role.arn
  description   = "Glue crawler for processing Meraki device data"
  schedule      = "cron(0 0 * * ? *)" # Runs daily at midnight UTC

  s3_target {
    path = var.s3_path
  }

  table_prefix = var.table_prefix
  recrawl_policy {
    recrawl_behavior = "CRAWL_EVERYTHING"  # Ensures it crawls all sub-folders
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "LOG"
  }

  tags = var.resource_tags
}
