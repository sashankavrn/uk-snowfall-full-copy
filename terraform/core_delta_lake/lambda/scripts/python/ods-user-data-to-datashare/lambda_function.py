import boto3
import os
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
sns = boto3.client('sns')

# Environment Variables
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET")  # Raw bucket
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")  # Datashare bucket
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

SOURCE_PREFIX = 'ods/user_data'
TARGET_PREFIX = 'ods_user_data'


def send_sns_notification(subject, message):
    try:
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        logger.info(f"SNS notification sent: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")


def clean_target_folder(prefix):
    try:
        response = s3.list_objects_v2(Bucket=TARGET_BUCKET, Prefix=prefix)
        if 'Contents' in response:
            for obj in response['Contents']:
                s3.delete_object(Bucket=TARGET_BUCKET, Key=obj['Key'])
                logger.info(f"Deleted old file: {obj['Key']}")
        else:
            logger.info(f"No existing files to delete under: {prefix}")
    except Exception as e:
        logger.error(f"Error cleaning target folder {prefix}: {str(e)}")
        raise


def lambda_handler(event, context):
    for record in event['Records']:
        source_key = record['s3']['object']['key']

        if not source_key.startswith(SOURCE_PREFIX) or not source_key.endswith('.csv'):
            logger.info(f"Skipping non-csv or unrelated file: {source_key}")
            continue

        destination_key = source_key.replace(SOURCE_PREFIX, TARGET_PREFIX, 1)

        try:
            # Clean the target folder before uploading
            clean_target_folder(TARGET_PREFIX)

            # Check if file already exists
            try:
                s3.head_object(Bucket=TARGET_BUCKET, Key=destination_key)
                logger.warning(f"Overwriting existing file: {destination_key}")
            except s3.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.info(f"No existing file found. Proceeding to copy: {destination_key}")
                else:
                    raise

            # Copy to target
            s3.copy_object(
                Bucket=TARGET_BUCKET,
                CopySource={'Bucket': SOURCE_BUCKET, 'Key': source_key},
                Key=destination_key
            )
            logger.info(f"Copied {source_key} to {destination_key}")

            # Delete from source
            s3.delete_object(Bucket=SOURCE_BUCKET, Key=source_key)
            logger.info(f"Deleted original file: {source_key}")

        except Exception as e:
            error_msg = f"Error processing file {source_key}: {str(e)}"
            logger.error(error_msg)
            send_sns_notification(
                subject="File Transfer Failure - Sopra to NCR",
                message=error_msg
            )
            raise e
