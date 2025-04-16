import boto3
import os
import urllib.parse
import logging

# Initialize clients
s3 = boto3.client('s3')
sns = boto3.client('sns')

# Environment variables
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Valid prefixes to accept
SUPPORTED_PREFIXES = [
    "ncr_service_now/change_request/",
    "ncr_service_now/incident/daily/",
    "ncr_service_now/incident/intraday/",
    "ncr_service_now/problem_record/",
    "ncr_service_now/service_case/",
    "ncr_service_now/incident_task/",
    "ncr_service_now/knowledge_base/",
    "ncr_service_now/knowledge/",
    "ncr_service_now/knowledge_feedback/",
    "ncr_service_now/knowledge_use/",
    "genesys/",
    "gcc/",
    "happysignals/"
]

def lambda_handler(event, context):
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote(event['Records'][0]['s3']['object']['key'])

        logger.info(f"Processing file: s3://{bucket}/{key}")

        if key.endswith('/'):
            logger.info("Folder detected. Skipping.")
            return

        # Check if prefix is valid
        matched_prefix = next((p for p in SUPPORTED_PREFIXES if key.startswith(p)), None)
        if not matched_prefix:
            raise Exception(f"Unrecognized prefix for file: {key}")

        # Check if file is a .parquet
        if not key.endswith('.parquet'):
            raise Exception(f"Invalid file extension. Only .parquet allowed: {key}")

        # Copy to target bucket (same key structure)
        s3.copy_object(
            Bucket=TARGET_BUCKET,
            CopySource={'Bucket': bucket, 'Key': key},
            Key=key
        )
        logger.info(f"Copied to target bucket: s3://{TARGET_BUCKET}/{key}")

        # Delete original from landing bucket
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Deleted original file from source: s3://{bucket}/{key}")

    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")

        # Move to error folder in same bucket
        try:
            error_key = f"error/{key}"
            s3.copy_object(
                Bucket=bucket,
                CopySource={'Bucket': bucket, 'Key': key},
                Key=error_key
            )
            s3.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Moved to error folder: s3://{bucket}/{error_key}")
        except Exception as move_error:
            logger.error(f"Failed to move to error folder: {str(move_error)}")

        # Send SNS notification
        send_sns_message(f"Error processing file {key}: {str(e)}")


def send_sns_message(message):
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject="Landing Bucket File Processing Error"
        )
        logger.info("SNS notification sent.")
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")
