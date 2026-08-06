resource "aws_lambda_layer_version" "jwt" {
  layer_name          = var.layer_name
  description         = var.description
  compatible_runtimes = var.compatible_runtimes
  filename            = "${path.module}/jwt_layer/layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/jwt_layer/layer.zip")
}
