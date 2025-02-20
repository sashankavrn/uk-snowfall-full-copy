import os
import json
import requests
import boto3
from datetime import datetime

# AWS Clients
s3 = boto3.client('s3')

# Read from Lambda Environment Variables
TARGET_BUCKET = os.getenv("TARGET_BUCKET")  # Provided by Terraform
S3_FOLDER = "meraki"  # Ensure files are stored in /meraki folder

# API Variables (Set in AWS Lambda Console)
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY")  
MERAKI_ORG_ID = os.getenv("MERAKI_ORG_ID")    

# API Headers
HEADERS = {
    "Authorization": f"Bearer {MERAKI_API_KEY}"
}

def fetch_meraki_data():
    """Fetch device data from the Meraki API"""
    url = f"https://api.meraki.com/api/v1/organizations/{MERAKI_ORG_ID}/devices"
    response = requests.get(url, headers=HEADERS, params={"perPage": 1000})

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error: {response.text}")

def save_to_s3(content):
    """Save JSON data to S3 in /meraki/ folder"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    s3_key = f"{S3_FOLDER}/device_list_{timestamp}.json"  # Ensure file is stored in /meraki/

    s3.put_object(
        Bucket=TARGET_BUCKET,
        Key=s3_key,
        Body=json.dumps(content, indent=2),
        ContentType="application/json"
    )
    return s3_key

def lambda_handler(event, context):
    """Lambda entry point"""
    try:
        data = fetch_meraki_data()
        s3_key = save_to_s3(data)

        return {"statusCode": 200, "body": json.dumps({"message": "Data saved", "s3_key": s3_key})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
