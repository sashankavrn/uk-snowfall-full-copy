import boto3
import json
import requests
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Initialize S3 client
s3_client = boto3.client('s3')

# Environment variables
DATASHARE_BUCKET = os.environ.get("DATASHARE_BUCKET")
NCR_API_ENDPOINT = os.environ.get("NCR_API_ENDPOINT")  # NCR API URL
TARGET_FOLDER = "rapid-newrelic-rmp-metrics/"

def lambda_handler(event, context):
    if not DATASHARE_BUCKET or not NCR_API_ENDPOINT:
        logger.error("Missing required environment variables: DATASHARE_BUCKET or NCR_API_ENDPOINT")
        return {
            'statusCode': 500,
            'body': 'Error: Missing required environment variables.'
        }

    collected_data = []

    for record in event['Records']:
        source_key = record['s3']['object']['key']

        # Ensure only files from /rapid-newrelic-rmp-metrics/ are processed
        if not source_key.startswith(TARGET_FOLDER):
            logger.info(f"Skipping file {source_key}, not in the {TARGET_FOLDER} folder.")
            continue
        
        file_data = read_s3_file(DATASHARE_BUCKET, source_key)
        if file_data:
            collected_data.append({"file": source_key, "data": file_data})

    if collected_data:
        response = send_to_ncr_api(collected_data)
        return {
            'statusCode': response.status_code if response else 500,
            'body': response.text if response else "Error in sending data."
        }
    else:
        logger.info("No valid files to process.")
        return {
            'statusCode': 200,
            'body': 'No valid files found to process.'
        }

def read_s3_file(bucket_name, file_key):
    """Reads an S3 object and returns its content."""
    try:
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        return obj["Body"].read().decode("utf-8")
    except Exception as e:
        logger.error(f"Error reading file {file_key}: {str(e)}")
        return None

def send_to_ncr_api(data):
    """Sends collected S3 data to NCR API."""
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(NCR_API_ENDPOINT, data=json.dumps(data), headers=headers)
        logger.info(f"Sent data to NCR API {NCR_API_ENDPOINT}. Response: {response.status_code} {response.text}")
        return response
    except Exception as e:
        logger.error(f"Error sending data to NCR API: {str(e)}")
        return None
