# Zipping the lambda files

# data "archive_file" "landing_trigger_script" {
#  type        = "zip"
#  source_dir = "${path.module}/scripts/python/landing_trigger/"
#  output_path = "${path.module}/scripts/zips/landing-trigger.zip"
# }


resource "aws_lambda_function" "uk_snowfall_landing_function" {
    filename = "${path.module}/scripts/zips/${var.lambda_filename}"
    function_name = "uk-snowfall-landing-trigger-${var.lambda_name}-${var.environment}"
    role = var.role_assumed_arn
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    memory_size = 500
    timeout = 70
    description = "Move files from snowfall landing bucket into the raw bucket"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/${var.lambda_filename}")
    tags = var.resource_tags
    layers = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
      }
    }
}


