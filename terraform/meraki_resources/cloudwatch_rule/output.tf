output "cloudwatch_rule_arn" {
  value = aws_cloudwatch_event_rule.daily_lambda_trigger.arn
}
