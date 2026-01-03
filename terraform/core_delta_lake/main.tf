terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.33.0"
    }
  }

  backend "s3" {
    key     = "snowfall-data-pipeline/core_delta_lake/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }


}

#Picks up from secrets in github
provider "aws" {
  region      = var.AWS_REGION
}



  # Picks up from secrets in github
  # provider "aws" {
  #   region      = var.AWS_REGION
  #   access_key = ""
  #   secret_key = "1"
  #   token = ""
  # }
  

# Triggering the S3 Module
module "s3_module_main" {
  source                          = "./s3/main_bucket"
  environment                     = var.environment
  account_number                  = var.account_number
  resource_tags                   = merge(var.resource_tags, { Environment = var.environment,DataClassification = "highly restricted" })
  role_assumed_arn                = var.role_assumed_arn
  lambda_landing_func_arn         = module.lambda_module.landing_trigger_arn
  lambda_permission               = module.lambda_module.lambda_s3_permission
  ods_user_data_lambda_arn        = module.lambda_module.ods_user_data_to_datashare_arn
  ods_user_data_lambda_permission = module.lambda_module.ods_user_data_to_datashare_permission
}

# Triggering the Lambda module
module "lambda_module" {
  source             = "./lambda"
  environment        = var.environment
  resource_tags      = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn   = var.role_assumed_arn
  landing_bucket_arn = module.s3_module_main.landing_bucket_arn
  raw_bucket_arn = module.s3_module_main.raw_bucket_arn
  sns_topic_arn      = module.sns_module.snowfall_topic_arn
  account_number     = var.account_number
  artifact_bucket_arn = module.s3_module_main.artifact_bucket_bucket_arn
  meraki_schedule = var.meraki_schedule
  newrelic_10min_schedule = var.newrelic_10min_schedule
  newrelic_5min_schedule = var.newrelic_5min_schedule
  newrelic_1am_schedule = var.newrelic_1am_schedule
  service_agent_bucket_arn = module.s3_module_main.service_agent_bucket_arn
  websocket_endpoint = module.websocket_api_module.websocket_endpoint
}   

# Triggering the SNS Module, will have to change to fix endpoint as email
module "sns_module" {
  source        = "./sns"
  environment   = var.environment
  resource_tags = merge(var.resource_tags, { Environment = var.environment })
  prod_email     = var.prod_email  
  not_prod_email = var.not_prod_email
}

module "appflow_module" {
  source        = "./appflow"
  environment             = var.environment
  resource_tags           = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn        = var.role_assumed_arn
  landing_bucket_arn      = module.s3_module_main.landing_bucket_arn
  sns_topic_arn           = module.sns_module.snowfall_topic_arn
  account_number          = var.account_number
  connector_profile_name  = var.connector_profile_name
  landing_bucket_name     = module.s3_module_main.landing_bucket_name
}

module "api_module" {
  source        = "./api"
  environment             = var.environment
  resource_tags           = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn        = var.role_assumed_arn
  account_number          = var.account_number
  service_agent_func_arn = module.lambda_module.service_agent_arn
  stage_name = var.stage_name
  
  depends_on = [module.lambda_module]
}

module "websocket_api_module" {
  source = "./websocketapi"

  environment        = var.environment
  resource_tags      = merge(var.resource_tags, { Environment = var.environment })
  role_assumed_arn   = var.role_assumed_arn
  stage_name         = var.stage_name
  account_number     = var.account_number

  connect_lambda_arn    = module.lambda_module.connect_lambda_arn
  disconnect_lambda_arn = module.lambda_module.disconnect_lambda_arn
  default_lambda_arn    = module.lambda_module.default_lambda_arn

   depends_on = [module.lambda_module]
}



