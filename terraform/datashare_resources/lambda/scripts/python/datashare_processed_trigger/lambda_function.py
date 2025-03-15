import boto3
import logging
import os
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize S3 client
s3_client = boto3.client('s3')

# Fetch bucket names from environment variables
PROCESSED_BUCKET = os.environ.get("PROCESSED_BUCKET")  # Source bucket
DATASHARE_PROCESSED_BUCKET = os.environ.get("DATASHARE_PROCESSED_BUCKET")  # Destination bucket

# Define folders to sync
FOLDERS_TO_SYNC = [
    "amazon_connect/",
    "service_now/change_request/",
    "service_now/incident/intraday/",
    "service_now/incident/daily/",
    "service_now/location/",
    "service_now/problem_record/",
    "service_now/service_request/",
    "service_now/service_offering/",
    "service_now/sys_user_group/",
    "service_now/sys_user/",
    "ods/trading_hours/",
    "ods/location_hierarchy/",
    "ods/adj_trading_hours/",
    "meraki/",
    "newrelic_rmp_device/"
]

# Lambda maximum execution time tracking
MAX_EXECUTION_TIME = 14 * 60  # 14 minutes (in seconds)

def lambda_handler(event, context):
    start_time = time.time()  # Track execution start time
    
    if not PROCESSED_BUCKET or not DATASHARE_PROCESSED_BUCKET:
        logger.error("Missing required environment variables: PROCESSED_BUCKET or DATASHARE_PROCESSED_BUCKET")
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }

    # Get the existing files in the destination bucket
    destination_objects = get_existing_files(DATASHARE_PROCESSED_BUCKET)

    for record in event['Records']:
        source_key = record['s3']['object']['key']

        # Track elapsed execution time
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_EXECUTION_TIME:
            logger.error(f"Execution time exceeded 14 minutes. Aborting! Elapsed Time: {elapsed_time:.2f} seconds")
            return {
                'statusCode': 500,
                'body': f"Execution took too long ({elapsed_time:.2f} seconds). Process stopped."
            }

        # Check if the file belongs to a valid folder
        folder_matched = next((folder for folder in FOLDERS_TO_SYNC if source_key.startswith(folder)), None)
        if not folder_matched:
            logger.info(f"Skipping file {source_key}, not in the allowed folders.")
            continue

        # Skip if the file already exists and is up to date
        if is_file_up_to_date(PROCESSED_BUCKET, DATASHARE_PROCESSED_BUCKET, source_key, destination_objects):
            logger.info(f"Skipping {source_key}, already exists and is up to date.")
            continue

        # Copy the file since it's new or modified
        copy_source = {
            'Bucket': PROCESSED_BUCKET,
            'Key': source_key
        }

        try:
            s3_client.copy_object(
                Bucket=DATASHARE_PROCESSED_BUCKET,
                CopySource=copy_source,
                Key=source_key
            )
            logger.info(f"Copied {source_key} from {PROCESSED_BUCKET} to {DATASHARE_PROCESSED_BUCKET}")

        except Exception as e:
            logger.error(f"Error copying {source_key}: {str(e)}")

    return {
        'statusCode': 200,
        'body': 'Incremental sync completed successfully.'
    }

def get_existing_files(bucket_name):
    """Returns a dictionary of existing files in the destination bucket with their last modified timestamps."""
    existing_files = {}
    paginator = s3_client.get_paginator("list_objects_v2")
    
    for page in paginator.paginate(Bucket=bucket_name):
        if "Contents" in page:
            for obj in page["Contents"]:
                existing_files[obj["Key"]] = obj["LastModified"]
    
    return existing_files

def is_file_up_to_date(source_bucket, destination_bucket, file_key, destination_objects):
    """Checks if a file in the source bucket is newer than the one in the destination bucket."""
    if file_key not in destination_objects:
        return False  # File is missing in destination, so it needs to be copied.

    source_metadata = s3_client.head_object(Bucket=source_bucket, Key=file_key)
    source_last_modified = source_metadata["LastModified"]

    destination_last_modified = destination_objects[file_key]

    return source_last_modified <= destination_last_modified  # If source is older or same, no need to copy.
