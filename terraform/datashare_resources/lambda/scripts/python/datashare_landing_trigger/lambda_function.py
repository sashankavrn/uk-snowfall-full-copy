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
LANDING_BUCKET = os.environ.get('LANDING_BUCKET')
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

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
    mappings = load_key_mapping()

    try:
        for mapping in mappings:
            prefix = mapping["fileName"].rstrip("/")
            destination = mapping["destinationPath"].rstrip("/")

            logger.info(f"Scanning prefix: {prefix}")
            response = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix=prefix)
            contents = response.get("Contents", [])

            data_files = [
                obj["Key"] for obj in contents
                if not obj["Key"].endswith("/") and "_PLACEHOLDER" not in obj["Key"]
            ]

            if not data_files:
                logger.info(f"No files found in prefix: {prefix}")
                continue

            for key in data_files:
                if key.endswith(".parquet"):
                    logger.info(f"Copying .parquet file: {key}")
                    base_moving(LANDING_BUCKET, key, TARGET_BUCKET, destination)
                    s3.delete_object(Bucket=LANDING_BUCKET, Key=key)
                    logger.info(f"Deleted: {key}")
                else:
                    logger.info(f"Skipping non-parquet file: {key}")

    except Exception as e:
        error_msg = f"Error in Lambda execution:\n{str(e)}"
        logger.error(error_msg)
        send_sns_notification(context, error_msg)
