data "archive_file" "snowfall_pipeline_zip" {
  type        = "zip"
  source_dir = "${path.module}/python/"
  output_path = "${path.module}/zips/snowfall_pipeline.zip"
}


################### Uplaoding Scripts to S3 #######################


resource "aws_s3_object" "main_runner_script" {
  bucket = var.artifact_bucket_name
  key    = "glue_script/main_runner.py" 
  source = "${path.module}/main_runner.py" 
  etag = filemd5("${path.module}/main_runner.py")
}


########### Uploading Libraries ######################

resource "aws_s3_object" "snowfall_pipeline_zip" {
  bucket = var.artifact_bucket_name
  key    = "glue_libraries/snowfall_pipeline.zip" 
  source = "${path.module}/zips/snowfall_pipeline.zip" 
  etag = filemd5("${path.module}/zips/snowfall_pipeline.zip")
}

########### Uploading Athena Views ######################
locals {
  athena_sql_files = fileset("${path.module}/athena_views", "*.sql")
}

resource "aws_s3_object" "athena_views" {
  for_each = { for file in local.athena_sql_files : file => file }

  bucket = var.artifact_bucket_name
  key    = "athena_views/${each.key}"
  source = "${path.module}/athena_views/${each.key}"
  etag   = filemd5("${path.module}/athena_views/${each.key}")
}
