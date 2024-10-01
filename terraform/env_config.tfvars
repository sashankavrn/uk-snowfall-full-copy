environments = {
  dev = {
    environment            = "dev"
    account_number         = "295446674139"
    role_assumed_arn       = "arn:aws:iam::295446674139:role/UK-MKT-DEV-GLUE-ROLE-CASE12585936411"
    terraform_bucket_name  = "eu-central1-dev-uk-snowfall-terraform-295446674139"
    connector_profile_name = "UK-SNowFall-ServiceNow-Connector-Prod"
  }

  nprod = {
  environment            = "nprod"
  account_number         = "404060908217"
  role_assumed_arn       = "arn:aws:iam::404060908217:role/UK-MKT-NProd-GLUE-ROLE"
  terraform_bucket_name  = "eu-central1-nprod-uk-snowfall-terraform-404060908217"
  connector_profile_name = "UK-SnowFall-ServiceNow-Prod"
  }

  prod = {
  environment            = "prod"
  account_number         = "868442188363"
  role_assumed_arn       = "arn:aws:iam::868442188363:role/UK-MKT-SNowfall-Prod-GLUE-SERV-ROLE"
  terraform_bucket_name  = "eu-central1-prod-uk-snowfall-terraform-868442188363"
  connector_profile_name = "UK-SnowFall-ServiceNow-Prod"
  }
}