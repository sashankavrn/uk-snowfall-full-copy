import boto3
import logging
import os
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize S3 client
s3_client = boto3.client('s3')

# Fetch bucket names from environment variables
DATASHARE_LANDING_BUCKET = os.environ.get("DATASHARE_LANDING_BUCKET")  # Source Bucket (Bucket A)
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")  # Destination Bucket (Bucket B)

# Define supported source prefixes and their corresponding destination prefixes
FOLDER_MAPPING = {
    "ncr_servicenow/": "ncr_servicenow/",
    "gcc/": "gcc/"
}

def lambda_handler(event, context):
    if not DATASHARE_LANDING_BUCKET or not TARGET_BUCKET:
        logger.error("Missing required environment variables: DATASHARE_LANDING_BUCKET or TARGET_BUCKET")
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }

    for record in event['Records']:
        # URL decode the key to handle spaces/special characters
        source_key = urllib.parse.unquote(record['s3']['object']['key'])
        logger.info(f"Received file: {source_key}")

        # Determine the destination key based on FOLDER_MAPPING
        destination_key = None
        for src_prefix, dest_prefix in FOLDER_MAPPING.items():
            if source_key.startswith(src_prefix):
                destination_key = source_key.replace(src_prefix, dest_prefix, 1)
                break

        if destination_key is None:
            logger.info(f"Skipping file {source_key}, not in recognized source folders.")
            continue

        copy_source = {
            'Bucket': DATASHARE_LANDING_BUCKET,
            'Key': source_key
        }

        try:
            # Copy the file to the target bucket under the mapped destination key
            s3_client.copy_object(
                Bucket=TARGET_BUCKET,
                CopySource=copy_source,
                Key=destination_key
            )
            logger.info(f"Copied {source_key} from {DATASHARE_LANDING_BUCKET} to {destination_key} in {TARGET_BUCKET}")

            # Delete the file from the source bucket and log the response for confirmation
            delete_response = s3_client.delete_object(Bucket=DATASHARE_LANDING_BUCKET, Key=source_key)
            logger.info(f"Delete response for {source_key}: {delete_response}")

        except Exception as e:
            logger.error(f"Error processing {source_key}: {str(e)}")
            # Optionally add error handling logic here

    return {
        'statusCode': 200,
        'body': 'File processing completed successfully.'
    }
