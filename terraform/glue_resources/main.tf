terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.33.0"
    }
  }

  backend "s3" {
    key     = "snowfall-data-pipeline/glue_resources/terraform.tfstate"
    region  = "eu-central-1"
    encrypt = true
  }
}

data "terraform_remote_state" "core_module" {
  backend = "s3"
  config = {
    bucket = var.terraform_bucket_name
    key    = "snowfall-data-pipeline/core_delta_lake/terraform.tfstate"
    region = "eu-central-1"
  }
}

# Provider configuration
provider "aws" {
  region = var.AWS_REGION
}

# Triggering the Scripts module
module "scripts_module" {
  source = "./scripts"
  artifact_bucket_name = data.terraform_remote_state.core_module.outputs.artifact_bucket_name
}

# Main Glue job runner script
resource "aws_glue_job" "main_runner_script" {
  name     = "uk-snowfall-main-script-runner"
  role_arn = var.role_assumed_arn
  tags     = var.resource_tags
  glue_version = "4.0"
  max_capacity = 4
  timeout     = 180
  description = "Main driver script for all pipelines"

  command {
    script_location = module.scripts_module.output_main_runner_script_path
    python_version  = 3
  }

  default_arguments = {
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-continuous-log-filter"      = "true"
    "--enable-metrics"                    = "true"
    "--enable-observability-metrics"      = "true"
    "--datalake-formats"                  = "delta"
    "--enable-auto-scaling"               = "true"
    "--conf"                              = "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog"
    "--SNS_TOPIC_ARN"                     = data.terraform_remote_state.core_module.outputs.snowfall_topic_arn
    "--TempDir"                           = data.terraform_remote_state.core_module.outputs.temporary_folder_path
    "--extra-py-files"                    = module.scripts_module.output_libraries_path
    "--ACCOUNT_NUMBER"                    = var.account_number
    "--ENVIRONMENT"                       = var.environment
  }

  execution_property {
    max_concurrent_runs = 100
  }
}

# Workflow details in the workflows/main.tf file
module "workflows" {
  source = "./workflows/glue_workflow"
  resource_tags = merge(var.resource_tags,{Environment = var.environment})
  glue_job_name = aws_glue_job.main_runner_script.name
}

############ Glue Data Catalog Databases #########

resource "aws_glue_catalog_database" "databases" {
  for_each = {
    "preparation" = "uk_snowfall_preparation"
    "processed"   = "uk_snowfall_processed"
    "semantic"    = "uk_snowfall_semantic"
    "microstrategy" = "uk_snowfall_microstrategy"
  }

  name        = each.value
  description = "Datasets that have been ${each.key == "preparation" ? "cleansed and validated" : each.key == "processed" ? "transformed and enriched" : each.key == "semantic" ? "aggregated and available for reporting" : "a playground for MicroStrategy"}"

  lifecycle {
    ignore_changes = [name, description]
    prevent_destroy = true  # Prevent the database from being destroyed
  }
}
