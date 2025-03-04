output "cloudwatch_rule_arn" {
  value = aws_cloudwatch_event_rule.hourly_lambda_trigger.arn
}

output "cloudwatch_rule_arn_meraki" {
  value = aws_cloudwatch_event_rule.meraki_event_rule.arn
}

