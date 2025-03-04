# Send notifications to EventBridge for all events in the bucket
# Bucket must exist before attaching a notification, will also 
# target a glue workflow which must too exist before attaching.


data "terraform_remote_state" "core_module" {
  backend = "s3"

  config = {
    bucket = var.terraform_bucket_name
    key     = "snowfall-data-pipeline/core_delta_lake/terraform.tfstate"
    region = "eu-central-1"
  }
}

data "terraform_remote_state" "glue_module" {
  backend = "s3"

  config = {
    bucket = var.terraform_bucket_name
    key     = "snowfall-data-pipeline/glue_resources/terraform.tfstate"
    region = "eu-central-1"
  }
}

locals {
  workflow_trigger_arns = data.terraform_remote_state.glue_module.outputs.workflow_trigger_arns
}


resource "aws_cloudwatch_event_rule" "location_event_rule" {
  name = "uk-snowfall-location-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/location/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "location_rule" {
  rule      = aws_cloudwatch_event_rule.location_event_rule.name
  arn       = local.workflow_trigger_arns["location"]
  role_arn = var.role_assumed_arn

}


resource "aws_cloudwatch_event_rule" "amazon_connect_event_rule" {
  name = "uk-snowfall-amazon-connect-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "amazon_connect/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "amazon_connect_rule" {
  rule      = aws_cloudwatch_event_rule.amazon_connect_event_rule.name
  arn       = local.workflow_trigger_arns["amazon_connect"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "incident_intraday_event_rule" {
  name = "uk-snowfall-incident-intraday-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/incident/intraday/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "incident_intraday_rule" {
  rule      = aws_cloudwatch_event_rule.incident_intraday_event_rule.name
  arn       = local.workflow_trigger_arns["incident_intraday"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "location_hierarchy_event_rule" {
  name = "uk-snowfall-location-hierarchy-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "ods/location_hierarchy/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "location_hierarchy_rule" {
  rule      = aws_cloudwatch_event_rule.location_hierarchy_event_rule.name
  arn       = local.workflow_trigger_arns["location_hierarchy"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "incident_daily_event_rule" {
  name = "uk-snowfall-incident-daily-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/incident/daily/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "incident_daily_rule" {
  rule      = aws_cloudwatch_event_rule.incident_daily_event_rule.name
  arn       = local.workflow_trigger_arns["incident_daily"]
  role_arn = var.role_assumed_arn

}


resource "aws_cloudwatch_event_rule" "problem_record_event_rule" {
  name = "uk-snowfall-problem-record-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/problem_record/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "problem_record_rule" {
  rule      = aws_cloudwatch_event_rule.problem_record_event_rule.name
  arn       = local.workflow_trigger_arns["problem_record"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "service_offering_event_rule" {
  name = "uk-snowfall-service-offering-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/service_offering/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "service_offering_rule" {
  rule      = aws_cloudwatch_event_rule.service_offering_event_rule.name
  arn       = local.workflow_trigger_arns["service_offering"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "service_request_event_rule" {
  name = "uk-snowfall-service-request-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/service_request/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "service_request_rule" {
  rule      = aws_cloudwatch_event_rule.service_request_event_rule.name
  arn       = local.workflow_trigger_arns["service_request"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "sys_user_event_rule" {
  name = "uk-snowfall-sys-user-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/sys_user/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "sys_user_rule" {
  rule      = aws_cloudwatch_event_rule.sys_user_event_rule.name
  arn       = local.workflow_trigger_arns["sys_user"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "sys_user_group_event_rule" {
  name = "uk-snowfall-sys-user-group-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/sys_user_group/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "sys_user_group_rule" {
  rule      = aws_cloudwatch_event_rule.sys_user_group_event_rule.name
  arn       = local.workflow_trigger_arns["sys_user_group"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "adj_trading_hours_event_rule" {
  name = "uk-snowfall-adj-trading-hours-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "ods/adj_trading_hours/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "adj_trading_hours_rule" {
  rule      = aws_cloudwatch_event_rule.adj_trading_hours_event_rule.name
  arn       = local.workflow_trigger_arns["adj_trading_hours"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "trading_hours_event_rule" {
  name = "uk-snowfall-trading-hours-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "ods/trading_hours/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "trading_hours_rule" {
  rule      = aws_cloudwatch_event_rule.trading_hours_event_rule.name
  arn       = local.workflow_trigger_arns["trading_hours"]
  role_arn = var.role_assumed_arn

}

resource "aws_cloudwatch_event_rule" "change_request_event_rule" {
  name = "uk-snowfall-change-request-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "service_now/change_request/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "change_request_rule" {
  rule      = aws_cloudwatch_event_rule.change_request_event_rule.name
  arn       = local.workflow_trigger_arns["change_request"]
  role_arn = var.role_assumed_arn

}


######################################Meraki#################################################

resource "aws_cloudwatch_event_rule" "meraki_event_rule" {
  name = "uk-snowfall-meraki-trigger-rule"
  description   = "Object create events on bucket s3://${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"
  event_pattern = <<EOF
{
  "source": ["aws.s3"],
  "detail": {
    "bucket": {
      "name": ["${data.terraform_remote_state.core_module.outputs.raw_bucket_name}"]
    },
    "object": {
      "key": [{
        "prefix": "meraki/"
      }]
    }
  },
  "detail-type": ["Object Created"]
}
EOF
}

resource "aws_cloudwatch_event_target" "meraki_rule" {
  rule      = aws_cloudwatch_event_rule.change_request_event_rule.name
  arn       = local.workflow_trigger_arns["meraki"]
  role_arn = var.role_assumed_arn

}