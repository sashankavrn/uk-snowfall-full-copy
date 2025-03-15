terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.33.0"
    }
  }

  backend "s3" {
    key     = "snowfall-data-pipeline/datashare_resources/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }


}

#Picks up from secrets in github
provider "aws" {
  region      = var.AWS_REGION
}

# # Fetch the existing SNS topic ARN
# data "aws_sns_topic" "datashare_sns_topic" {
#   name = "uk-snowfall-notification-dev"  # Name of the existing SNS topic
# }


# Triggering the Datashare S3 Module
module "datashare_buckets" {
  source                  = "./s3/datashare_bucket"
  environment             = var.environment
  account_number          = var.account_number
  resource_tags           = merge(var.resource_tags, { Environment = var.environment, DataClassification = "highly restricted" })
  role_assumed_arn        = var.role_assumed_arn
  datashare_landing_trigger_arn = module.datashare_lambda_module.datashare_landing_trigger_lambda_arn
  allow_landing_trigger   = module.datashare_lambda_module.datashare_landing_trigger_lambda_s3_permission
}



# Triggering the Lambda Module
module "datashare_lambda_module" {
  source             = "./lambda"
  environment        = var.environment
  resource_tags      = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn   = var.role_assumed_arn
  datashare_landing_bucket_arn = module.datashare_buckets.datashare_landing_bucket_arn
  datashare_processed_bucket_arn = module.datashare_buckets.datashare_processed_bucket_arn
  # sns_topic_arn      = data.aws_sns_topic.datashare_sns_topic.arn
  account_number     = var.account_number
}




# # Triggering event bridge module
# module "event_bridge_module" {
#   source        = "./eventbridge"
#   environment   = var.environment
#   role_assumed_arn = var.role_assumed_arn
#   account_number = var.account_number
#   resource_tags = merge(var.resource_tags, { Environment = var.environment })
#   terraform_bucket_name   = var.terraform_bucket_name
# }






