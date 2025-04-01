import boto3
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize S3 client
s3_client = boto3.client('s3')

# Fetch bucket names from environment variables
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET")
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")

# Define folders to sync
FOLDERS_TO_SYNC = [
    "amazon_connect/",
    "meraki/",
    "newrelic/"
]

# Threshold (in milliseconds) to stop processing before Lambda timeout
TIME_THRESHOLD = 5000  # 5 seconds

def lambda_handler(event, context):
    if not SOURCE_BUCKET or not TARGET_BUCKET:
        logger.error("Missing required environment variables: SOURCE_BUCKET or TARGET_BUCKET")
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }
    
    for folder in FOLDERS_TO_SYNC:
        logger.info(f"Syncing folder: {folder}")
        
        # List objects in the source and target buckets for this folder
        source_objects = list_objects(SOURCE_BUCKET, folder, context)
        target_objects = list_objects(TARGET_BUCKET, folder, context)
        
        # Map target objects by key for easy lookup of LastModified times
        target_map = {obj['Key']: obj['LastModified'] for obj in target_objects}
        
        for src_obj in source_objects:
            # Check remaining time; if below threshold, exit gracefully.
            remaining_time = context.get_remaining_time_in_millis()
            if remaining_time < TIME_THRESHOLD:
                logger.warning(f"Approaching timeout: {remaining_time}ms remaining. Exiting sync early.")
                return {
                    'statusCode': 200,
                    'body': 'Sync incomplete: nearing timeout.'
                }
            
            key = src_obj['Key']
            src_last_modified = src_obj['LastModified']
            
            # If the object exists in the target and is up-to-date, skip it
            if key in target_map and src_last_modified <= target_map[key]:
                logger.info(f"Skipping {key}: already up-to-date.")
                continue
            
            # Copy the object from the source bucket to the target bucket
            copy_source = {'Bucket': SOURCE_BUCKET, 'Key': key}
            try:
                s3_client.copy_object(
                    Bucket=TARGET_BUCKET,
                    CopySource=copy_source,
                    Key=key
                )
                logger.info(f"Copied {key} from {SOURCE_BUCKET} to {TARGET_BUCKET}.")
            except Exception as e:
                logger.error(f"Error copying {key}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': 'Sync completed successfully.'
    }

def list_objects(bucket, prefix, context):
    """Lists objects under the specified bucket and prefix.
       If the function nears timeout during pagination, it breaks out early."""
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            objects.extend(page["Contents"])
        
        # Check for remaining time during pagination
        if context.get_remaining_time_in_millis() < TIME_THRESHOLD:
            logger.warning(f"Approaching timeout while listing objects in bucket {bucket} with prefix {prefix}.")
            break
    return objects
