import requests
import re
import json
import boto3
import time
import os
from datetime import datetime, timezone
from botocore.exceptions import BotoCoreError, ClientError

def get_secret():
    """Retrieve API key from AWS Secrets Manager."""
    secret_name = "uk-snowfall"
    region_name = "eu-central-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            return f"Bearer {secret['uk-snowfall-meraki-api-key']}"
        else:
            raise ValueError("SecretString not found in response")
    except (BotoCoreError, ClientError) as e:
        error_message = f"Failed to retrieve API key: {e}"
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return None

def notify_failure(message):
    """Send SNS notification for a failure event."""
    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        print("[ERROR] SNS_TOPIC_ARN not set in environment variables.")
        return

    try:
        sns_client = boto3.client('sns')
        sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject="Meraki Device Lambda Failure Notification"
        )
        print("[INFO] SNS notification sent.")
    except ClientError as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

def extract_restaurant_number(name):
    """Extract restaurant number from device name."""
    match = re.search(r'-(\d+)', name)
    return int(match.group(1)) if match else None

def merakiAPI(authToken, nextToken=None, retries=3):
    """Fetch Meraki devices using API with pagination."""
    url = "https://api.meraki.com/api/v1/organizations/662029145223463867/devices"
    params = {'perPage': '1000'}
    if nextToken:
        params['startingAfter'] = nextToken

    headers = {'Authorization': authToken}

    for attempt in range(retries):
        try:
            print(f"[INFO] Attempt {attempt+1}: Fetching Meraki devices...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            nextToken = None
            links = response.headers.get('Link', '').split(', ')
            for link in links:
                if 'rel=next' in link:
                    match = re.search(r'startingAfter=([^&]+)', link)
                    if match:
                        nextToken = match.group(1)
                        break

            return response.json(), nextToken

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] API request failed (Attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None, None

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    authToken = get_secret()
    if not authToken:
        error_message = "API Key retrieval failed."
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}

    deviceList = []
    nextToken = None
    sys_updated_timestamp = datetime.now(timezone.utc).isoformat()

    while True:
        devices, nextToken = merakiAPI(authToken, nextToken)
        if devices is None:
            error_message = "API is unreachable or returned no data. Aborting process."
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        for device in devices:
            device_data = {
                "name": device.get("name"),
                "serial": device.get("serial"),
                "mac": device.get("mac"),
                "networkId": device.get("networkId"),
                "productType": device.get("productType"),
                "model": device.get("model"),
                "address": device.get("address"),
                "lat": device.get("lat"),
                "lng": device.get("lng"),
                "notes": device.get("notes"),
                "tags": device.get("tags"),
                "wan1Ip": device.get("wan1Ip"),
                "wan2Ip": device.get("wan2Ip"),
                "configurationUpdatedAt": device.get("configurationUpdatedAt"),
                "firmware": device.get("firmware"),
                "url": device.get("url"),
                "details": device.get("details"),
                "restaurant_number": extract_restaurant_number(device.get("name", "")),
                "sys_updated_timestamp": sys_updated_timestamp
            }
            deviceList.append(device_data)

        if not nextToken:
            print("[INFO] No more devices to fetch. Exiting loop.")
            break

    json_data = json.dumps(deviceList, indent=4)
    current_time = datetime.now()
    filename = f"device_list_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    bucket_name = os.environ.get('TARGET_BUCKET')
    s3_key = f"meraki/device_info/{filename}"

    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(Body=json_data, Bucket=bucket_name, Key=s3_key)
        print(f"[SUCCESS] Data uploaded to s3://{bucket_name}/{s3_key}")
        return {"statusCode": 200, "body": f"Data uploaded to {s3_key}"}
    except ClientError as e:
        error_message = f"Failed to upload data to S3: {e}"
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return {"statusCode": 500, "body": "S3 upload failed"}
