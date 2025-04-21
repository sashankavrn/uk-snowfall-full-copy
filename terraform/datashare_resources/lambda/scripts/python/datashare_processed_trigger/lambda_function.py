import boto3
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize AWS clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# Environment Variables
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET")
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# Define folders to sync
FOLDERS_TO_SYNC = [
    "amazon_connect/",
    "meraki/",
    "newrelic/newrelic_rmp_device_info/"
]

# Threshold (in milliseconds) to stop processing before Lambda timeout
TIME_THRESHOLD = 5000  # 5 seconds

# Send summary SNS notification
def send_sns_summary_notification(context, failures):
    if not failures:
        return

    subject = f"Lambda Failure Summary - {context.function_name}"
    message_lines = [
        f"One or more object copies failed during sync in Lambda: {context.function_name}",
        "",
        "Failures:"
    ]
    message_lines.extend(failures)
    message = "\n".join(message_lines)

    try:
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        logger.info(f"SNS summary notification sent: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send SNS summary notification: {str(e)}")

# Main Lambda handler
def lambda_handler(event, context):
    if not SOURCE_BUCKET or not TARGET_BUCKET:
        error_msg = "Missing required environment variables: SOURCE_BUCKET or TARGET_BUCKET"
        logger.error(error_msg)
        send_sns_summary_notification(context, [error_msg])
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }

    copy_failures = []

    for folder in FOLDERS_TO_SYNC:
        logger.info(f"Syncing folder: {folder}")
        
        source_objects = list_objects(SOURCE_BUCKET, folder, context)
        target_objects = list_objects(TARGET_BUCKET, folder, context)
        
        target_map = {obj['Key']: obj['LastModified'] for obj in target_objects}
        
        for src_obj in source_objects:
            remaining_time = context.get_remaining_time_in_millis()
            if remaining_time < TIME_THRESHOLD:
                logger.warning(f"Approaching timeout: {remaining_time}ms remaining. Exiting sync early.")
                send_sns_summary_notification(context, copy_failures)
                return {
                    'statusCode': 200,
                    'body': 'Sync incomplete: nearing timeout.'
                }

            key = src_obj['Key']
            src_last_modified = src_obj['LastModified']

            if key in target_map and src_last_modified <= target_map[key]:
                logger.info(f"Skipping {key}: already up-to-date.")
                continue

            copy_source = {'Bucket': SOURCE_BUCKET, 'Key': key}
            try:
                s3_client.copy_object(
                    Bucket=TARGET_BUCKET,
                    CopySource=copy_source,
                    Key=key
                )
                logger.info(f"Copied {key} from {SOURCE_BUCKET} to {TARGET_BUCKET}.")
            except Exception as e:
                error_msg = f"Error copying {key}: {str(e)}"
                logger.error(error_msg)
                copy_failures.append(error_msg)

    send_sns_summary_notification(context, copy_failures)

    return {
        'statusCode': 200,
        'body': 'Sync completed with errors.' if copy_failures else 'Sync completed successfully.'
    }

# List S3 objects with timeout awareness
def list_objects(bucket, prefix, context):
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            objects.extend(page["Contents"])
        if context.get_remaining_time_in_millis() < TIME_THRESHOLD:
            logger.warning(f"Approaching timeout while listing objects in bucket {bucket} with prefix {prefix}.")
            break
    return objects
