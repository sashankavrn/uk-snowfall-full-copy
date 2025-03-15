import boto3
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize S3 client
s3_client = boto3.client('s3')

# Fetch bucket names from environment variables
DATASHARE_LANDING_BUCKET = os.environ.get("DATASHARE_LANDING_BUCKET")  # Source bucket
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")  # Destination bucket

# Folder paths in S3
SOURCE_PREFIX = "ncr_servicenow/"
DESTINATION_PREFIX = "ncr_servicenow/"

def lambda_handler(event, context):
    if not DATASHARE_LANDING_BUCKET or not TARGET_BUCKET:
        logger.error("Missing required environment variables: DATASHARE_LANDING_BUCKET or TARGET_BUCKET")
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }

    for record in event['Records']:
        source_key = record['s3']['object']['key']

        # Ensure only files from the correct folder are copied
        if not source_key.startswith(SOURCE_PREFIX):
            logger.info(f"Skipping file {source_key}, not in the expected source path.")
            continue
        
        # Define destination key (same file name in destination)
        destination_key = source_key.replace(SOURCE_PREFIX, DESTINATION_PREFIX, 1)

        copy_source = {
            'Bucket': DATASHARE_LANDING_BUCKET,
            'Key': source_key
        }

        try:
            # Copy file to destination bucket
            s3_client.copy_object(
                Bucket=TARGET_BUCKET,
                CopySource=copy_source,
                Key=destination_key
            )
            logger.info(f"Copied {source_key} from {DATASHARE_LANDING_BUCKET} to {destination_key} in {TARGET_BUCKET}")

        except Exception as e:
            logger.error(f"Error copying {source_key} to {destination_key}: {str(e)}")

    return {
        'statusCode': 200,
        'body': 'File copy process completed successfully.'
    }
