# Zipping the lambda files

# data "archive_file" "landing_trigger_script" {
#  type        = "zip"
#  source_dir = "${path.module}/scripts/python/${var.lambda_filename}/"
#  output_path = "${path.module}/scripts/zips/${var.lambda_filename}.zip"
# }


resource "aws_lambda_function" "uk_snowfall_landing_function" {
    filename = "${path.module}/scripts/zips/${var.lambda_filename}.zip"
    function_name = "uk-snowfall2-${var.lambda_name}-${var.environment}"
    role = var.role_assumed_arn
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    memory_size = 500
    timeout = 70
    description = "snowfall2 lambda"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/${var.lambda_filename}.zip")
    tags = var.resource_tags
    layers = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall2-landing-${var.account_number}"
        SOURCE_BUCKET =  "eu-central1-${var.environment}-uk-snowfall2-processed-${var.account_number}"
      }
    }
}


