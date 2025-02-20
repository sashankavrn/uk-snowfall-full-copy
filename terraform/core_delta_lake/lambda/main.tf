# Zipping the lambda files

data "archive_file" "landing_trigger_script" {
  type        = "zip"
  source_dir = "${path.module}/scripts/python/landing_trigger/"
  output_path = "${path.module}/scripts/zips/landing-trigger.zip"
}


resource "aws_lambda_function" "uk_snowfall_landing_function" {
    filename = "${path.module}/scripts/zips/landing-trigger.zip"
    function_name = "uk-snowfall-landing-trigger-${var.environment}"
    role = var.role_assumed_arn
    handler = "lambda_function.lambda_handler"
    runtime = "python3.12"
    memory_size = 500
    timeout = 70
    description = "Move files from snowfall landing bucket into the raw bucket"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/landing-trigger.zip")
    tags = var.resource_tags
    layers = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]
    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-raw-${var.account_number}"
        SNS_TOPIC_ARN = var.sns_topic_arn
      }
    }
}

## Adding permissions for lambda
resource "aws_lambda_permission" "allow_landing_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.uk_snowfall_landing_function.arn
  principal     = "s3.amazonaws.com"
  source_arn    = var.landing_bucket_arn
  depends_on = [ var.landing_bucket_arn,aws_lambda_function.uk_snowfall_landing_function ]
}
# lambda  for new Datasourses - meraki 

# s3 policy for lambda 
# resource "aws_iam_policy" "lambda_s3_write_policy" {
#   name        = "LambdaS3WritePolicy"
#   description = "Allows Lambda to write data to the S3 /meraki folder"

#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect   = "Allow"
#         Action   = ["s3:PutObject"]
#         Resource = "arn:aws:s3:::eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}/meraki/*"
#       }
#     ]
#   })
# }

# Attach IAM Policy to Lambda Role
resource "aws_iam_role_policy_attachment" "lambda_s3_attach" {
  role       = var.role_assumed_arn
  # policy_arn = aws_iam_policy.lambda_s3_write_policy.arn
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"   #using this untill role is fixed 
}

data "archive_file" "retrieve_data_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/scripts/python/retrieve_data/"
  output_path = "${path.module}/scripts/zips/retrieve-data.zip"
}

resource "aws_lambda_function" "uk_snowfall_data_retrieval_function" {
    filename         = "${path.module}/scripts/zips/retrieve-data.zip"
    function_name    = "uk-snowfall-data-retrieval-${var.environment}"
    role            = var.role_assumed_arn
    handler         = "lambda_function.lambda_handler"
    runtime         = "python3.12"
    memory_size     = 500
    timeout         = 70
    description     = "Fetch Meraki data and save to S3 /meraki folder"
    source_code_hash = filebase64sha256("${path.module}/scripts/zips/retrieve-data.zip")
    tags            = var.resource_tags
    layers          = ["arn:aws:lambda:eu-central-1:336392948345:layer:AWSSDKPandas-Python312:1"]

    environment {
      variables = {
        TARGET_BUCKET = "eu-central1-${var.environment}-uk-snowfall-landing-${var.account_number}"
      }
    }
}
