import boto3
import os
import json
import logging
import urllib.parse
from base_moving import base_moving

# Initialize AWS clients
s3 = boto3.client('s3')

# Logging setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
LANDING_BUCKET = os.environ.get('LANDING_BUCKET')
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')

# Load mapping.json
def load_key_mapping():
    with open('mapping.json', 'r') as file:
        mappings = json.load(file)
    return mappings.get("fileMappings", [])

# Determine destination path based on fileName match
def match_mapping(key, mappings):
    for mapping in mappings:
        if mapping["fileName"] in key:
            return mapping["destinationPath"]
    return None

def lambda_handler(event, context):
    mappings = load_key_mapping()

    try:
        # List all prefixes in the mappings
        for mapping in mappings:
            prefix = mapping["fileName"]
            destination = mapping["destinationPath"]

            logger.info(f"Scanning prefix: {prefix}")
            response = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix=prefix)
            contents = response.get("Contents", [])

            # Filter out folders and placeholders
            data_files = [
                obj["Key"] for obj in contents
                if not obj["Key"].endswith("/") and "_PLACEHOLDER" not in obj["Key"]
            ]

            if not data_files:
                logger.info(f"No files found in prefix: {prefix}")
                ensure_placeholder(prefix)
                continue

            for key in data_files:
                if key.endswith(".parquet"):
                    logger.info(f"Copying .parquet file: {key}")
                    base_moving(LANDING_BUCKET, key, TARGET_BUCKET, destination)
                    s3.delete_object(Bucket=LANDING_BUCKET, Key=key)
                    logger.info(f"Deleted: {key}")
                else:
                    logger.info(f"Skipping non-parquet file: {key}")

            # Add placeholder if nothing left in the prefix
            remaining = s3.list_objects_v2(Bucket=LANDING_BUCKET, Prefix=prefix).get("Contents", [])
            remaining_files = [
                o["Key"] for o in remaining
                if not o["Key"].endswith("/") and "_PLACEHOLDER" not in o["Key"]
            ]
            if not remaining_files:
                ensure_placeholder(prefix)

    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")

# Optional: Keep folder visible in console
def ensure_placeholder(prefix):
    placeholder_key = f"{prefix}/_PLACEHOLDER"
    s3.put_object(Bucket=LANDING_BUCKET, Key=placeholder_key, Body=b"")
    logger.info(f"Added placeholder: s3://{LANDING_BUCKET}/{placeholder_key}")
