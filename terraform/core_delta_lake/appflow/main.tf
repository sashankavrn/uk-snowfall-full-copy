resource "null_resource" "create_appflow" {
    count = 1
    provisioner "local-exec" {
        command = "python3 ${path.module}/create_appflow.py"
        
        environment = {
          LandingBucket = var.landing_bucket_name
          ConnectorProfileName = var.connector_profile_name
        }
    }
    triggers = {
        flow_config_hash = filemd5("${path.module}/flow_config.json")
    }
}

resource "null_resource" "delete_appflow" {
    count = 1
    provisioner "local-exec" {
        command = "python3 ${path.module}/delete_appflow.py"
        when = destroy
    }
}