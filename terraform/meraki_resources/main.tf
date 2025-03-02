terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.33.0"
    }
  }

  backend "s3" {
    key     = "snowfall-data-pipeline/meraki/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }


}

#Picks up from secrets in github
provider "aws" {
  region      = var.AWS_REGION
}

  

# Triggering the Lambda Module
module "lambda_landing_trigger" {
  source             = "./lambda"
  lambda_filename    = "Snowfall_Get_Device_Info_From_Meraki"
  lambda_name        = "uk-snowfall-meraki-Device-Info"
  environment        = var.environment
  resource_tags      = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn   = var.role_assumed_arn
  landing_bucket_arn = "arn:aws:s3:::eu-central1-dev-uk-snowfall-landing-295446674139"
  account_number = var.account_number
}


module "lambda_processing_trigger" {
  source             = "./lambda"
  environment        = var.environment
  lambda_filename    = "Snowfall_Process_Meraki_Data"
  lambda_name        = "uk-snowfall-meraki-process-Info"
  resource_tags      = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn   = var.role_assumed_arn
  landing_bucket_arn = "arn:aws:s3:::eu-central1-dev-uk-snowfall-processed-295446674139"
  account_number     = var.account_number
}

resource "aws_lambda_permission" "allow_landing_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_landing_trigger.lambda_arn
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::eu-central1-dev-uk-snowfall-landing-295446674139"
}

resource "aws_lambda_permission" "allow_processing_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_processing_trigger.lambda_arn
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::eu-central1-dev-uk-snowfall-processed-295446674139"
}

module "cloudwatch_lambda_trigger" {
  source             = "./cloudwatch_rule"
  environment        = var.environment
  lambda_function_arn = module.lambda_landing_trigger.lambda_arn
  # aws_role_to_assume  = var.aws_role_to_assume
  processing_lambda_arn = module.lambda_processing_trigger.lambda_arn
}

module "glue" {
  source        = "./glue"
  environment   = var.environment
  database_name = "uk_snowfall-meraki_dev"
  table_prefix  = "uk_snowfall-device_info"
  s3_path       = "s3://snowfall-dev-meraki-processed/meraki/"
  s3_bucket_arn = "arn:aws:s3:::eu-central1-dev-uk-snowfall-processed-295446674139"
  aws_region    = var.AWS_REGION
  account_id    = var.account_number
  resource_tags = merge(var.resource_tags, { Name = "meraki-glue-crawler" })
}

# Triggering the S3 Module
module "s3_module_main" {
  source                  = "./s3"
  environment             = var.environment
  account_number          = var.account_number
  resource_tags           = merge(var.resource_tags, { Environment = var.environment, DataClassification = "highly restricted" })
  role_assumed_arn        = var.role_assumed_arn
  lambda_landing_func_arn = module.lambda_landing_trigger.lambda_arn  #
  lambda_permission       = aws_lambda_permission.allow_landing_bucket.id  # Pass Lambda permission
}

