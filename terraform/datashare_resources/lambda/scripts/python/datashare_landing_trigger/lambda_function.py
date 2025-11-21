import boto3
import os
import json
import logging
from base_moving import base_moving

# AWS Clients
s3 = boto3.client('s3')
sns = boto3.client('sns')

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment Variables
LANDING_BUCKET = os.environ.get('LANDING_BUCKET')               # Source bucket
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')                 # Main destination
TECH360_TARGET_BUCKET = os.environ.get('TECH360_TARGET_BUCKET') # Tech360 destination
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')                 # Notification topic

# Validate environment variables
if not all([LANDING_BUCKET, TARGET_BUCKET, TECH360_TARGET_BUCKET, SNS_TOPIC_ARN]):
    raise ValueError("Missing one or more required environment variables.")

# Prefixes to copy to TECH360 bucket only
TECH360_PREFIXES = {
    "ncr_service_now/incident/",
    "ncr_service_now/problem_record/",
    "ncr_service_now/service_case/"
    "ncr_service_now/workenotes/"
}

# Load mapping.json
def load_key_mapping():
    with open('mapping.json', 'r') as file:
        mappings = json.load(file)
    return mappings.get("fileMappings", [])

# Send SNS notification on failure
def send_sns_notification(context, error_message):
    subject = f"Lambda Failure - {context.function_name}"
    try:
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=error_message
        )
        logger.info(f"SNS notification sent: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")

# Main Lambda Handler
def lambda_handler(event, context):
    request_id = context.aws_request_id
    mappings = load_key_mapping()

    try:
        for mapping in mappings:
            prefix = mapping["fileName"].rstrip("/")
            destination = mapping["destinationPath"].rstrip("/")

            logger.info(f"[{request_id}] Scanning prefix: {prefix}")
            paginator = s3.get_paginator('list_objects_v2')

            for page in paginator.paginate(Bucket=LANDING_BUCKET, Prefix=prefix):
                contents = page.get("Contents", [])

                data_files = [
                    obj["Key"] for obj in contents
                    if not obj["Key"].endswith("/")
                    and "_PLACEHOLDER" not in obj["Key"]
                    and obj["Key"].startswith(prefix + "/")
                ]

                if not data_files:
                    logger.info(f"[{request_id}] No files found in prefix: {prefix}")
                    continue

                for key in data_files:
                    try:
                        if key.endswith(".parquet"):
                            # Always copy to TARGET_BUCKET
                            logger.info(f"[{request_id}] Copying to TARGET_BUCKET: {key}")
                            base_moving(LANDING_BUCKET, key, TARGET_BUCKET, destination)

                            # Conditionally copy to TECH360_TARGET_BUCKET
                            if prefix + "/" in TECH360_PREFIXES:
                                logger.info(f"[{request_id}] Copying to TECH360_TARGET_BUCKET: {key}")
                                base_moving(LANDING_BUCKET, key, TECH360_TARGET_BUCKET, destination)

                            # Delete original
                            s3.delete_object(Bucket=LANDING_BUCKET, Key=key)
                            logger.info(f"[{request_id}] Deleted: {key}")
                        else:
                            logger.info(f"[{request_id}] Skipping non-parquet file: {key}")
                    except Exception as file_error:
                        logger.error(f"[{request_id}] Error processing file {key}: {str(file_error)}")

    except Exception as e:
        error_msg = f"[{request_id}] Error in Lambda execution:\n{str(e)}"
        logger.error(error_msg)
        send_sns_notification(context, error_msg)
