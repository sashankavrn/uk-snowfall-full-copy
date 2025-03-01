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



  # #Picks up from secrets in github
  # provider "aws" {
  #   region      = var.AWS_REGION
  #   access_key = ""
  #   secret_key = "1"
  #   token = ""
  # }
  

# Triggering the Lambda Module
module "lambda_landing_trigger" {
  source             = "./lambda"
  lambda_filename    = "Snowfall_Get_Device_Info_From_Meraki.zip"
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
  lambda_filename    = "Snowfall_Process_Meraki_Data.zip"
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


