import boto3
import logging
import os
from datetime import datetime

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
    "ods/",
    "meraki/",
    "newrelic/newrelic_rmp_device_info/",
    "newrelic/newrelic_digital_gma_foe_response/",
    "newrelic/newrelic_digital_3po_foe_response/"
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

# List S3 objects with timeout awareness
def list_objects(bucket, prefix, context):
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            objects.extend(page["Contents"])
        else:
            logger.info(f"No objects found for prefix {prefix} in bucket {bucket}.")
        if context.get_remaining_time_in_millis() < TIME_THRESHOLD:
            logger.warning(f"Approaching timeout while listing objects in bucket {bucket} with prefix {prefix}.")
            break
    return objects

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
    total_files_copied = 0

    for folder in FOLDERS_TO_SYNC:
        logger.info(f"Syncing folder: {folder}")
        
        source_objects = list_objects(SOURCE_BUCKET, folder, context)
        target_objects = list_objects(TARGET_BUCKET, folder, context)

        # Map: key -> (LastModified, Size)
        target_map = {obj['Key']: (obj['LastModified'], obj['Size']) for obj in target_objects}

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
            src_size = src_obj['Size']

            if key in target_map:
                tgt_last_modified, tgt_size = target_map[key]
                if src_last_modified <= tgt_last_modified and src_size == tgt_size:
                    logger.info(f"Skipping {key}: already up-to-date.")
                    continue

            copy_source = {'Bucket': SOURCE_BUCKET, 'Key': key}
            try:
                s3_client.copy_object(
                    Bucket=TARGET_BUCKET,
                    CopySource=copy_source,
                    Key=key
                )
                total_files_copied += 1
                logger.info(f"Copied file: {key}")
                logger.info(f" - Size: {src_size} bytes")
                logger.info(f" - LastModified: {src_last_modified.isoformat()}")
            except Exception as e:
                error_msg = f"Error copying {key}: {str(e)}"
                logger.error(error_msg)
                copy_failures.append(error_msg)

    logger.info(f"Sync complete. Folders checked: {len(FOLDERS_TO_SYNC)}. Files copied: {total_files_copied}. Failures: {len(copy_failures)}")
    send_sns_summary_notification(context, copy_failures)

    return {
        'statusCode': 200,
        'body': 'Sync completed with errors.' if copy_failures else 'Sync completed successfully.'
    }
