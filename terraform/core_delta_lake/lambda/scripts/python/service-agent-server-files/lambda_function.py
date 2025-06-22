import boto3
import os
import logging

s3 = boto3.client('s3')
sns = boto3.client('sns')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SOURCE_BUCKET = os.environ.get('SOURCE_BUCKET')
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

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

def lambda_handler(event, context):
    if 'Records' not in event:
        logger.warning(f"No 'Records' key in event. Event was: {event}")
        return

    for record in event['Records']:
        source_bucket = record['s3']['bucket']['name']
        source_key = record['s3']['object']['key']

        if source_bucket != SOURCE_BUCKET:
            logger.warning(f"Ignoring event from unexpected bucket: {source_bucket}")
            continue

        # Prepend the target prefix to preserve full structure under uploads/
        target_key = f"service_agent_server_files/uploads/{source_key}"

        logger.info(f"Preparing to copy from s3://{SOURCE_BUCKET}/{source_key} to s3://{TARGET_BUCKET}/{target_key}")

        try:
            s3.copy_object(
                Bucket=TARGET_BUCKET,
                CopySource={'Bucket': SOURCE_BUCKET, 'Key': source_key},
                Key=target_key
            )
            logger.info(f"Successfully copied to s3://{TARGET_BUCKET}/{target_key}")
        except Exception as e:
            error_msg = f"Failed to copy {source_key} to {TARGET_BUCKET}/{target_key}: {str(e)}"
            logger.error(error_msg)
            send_sns_notification(
                subject=f"Lambda Copy Failure - {context.function_name}",
                message=error_msg
            )
