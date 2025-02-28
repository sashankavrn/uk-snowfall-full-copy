# output "glue_crawler_name" {
#   value = aws_glue_crawler.glue_crawler.name
# }

# output "glue_crawler_role_arn" {
#   value = aws_iam_role.glue_crawler_role.arn
# }
output "glue_database_name" {
  value = aws_glue_catalog_database.glue_database.name
}
