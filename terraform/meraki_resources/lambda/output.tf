output "lambda_arn" {
  value = aws_lambda_function.uk_snowfall_landing_function.arn
  description = "The landing trigger function ARN number"
}
