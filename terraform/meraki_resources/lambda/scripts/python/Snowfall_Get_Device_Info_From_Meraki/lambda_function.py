import requests
import re
import json
import boto3
import time
from datetime import datetime
from botocore.exceptions import BotoCoreError, ClientError

def get_secret():
    """Retrieve API key from AWS Secrets Manager."""
    secret_name = "uk-snowfall"  # Correct Secret Name
    region_name = "eu-central-1"  # AWS regionnnnn

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            return f"Bearer {secret['uk-snowfall-meraki-api-key']}"  # Extract correct key
        else:
            raise ValueError("SecretString not found in response")
    except (BotoCoreError, ClientError) as e:
        print(f"[ERROR] Failed to retrieve API key: {e}")
        return None

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
            response.raise_for_status()  # Raise HTTP error if response is not 2xx

            # Extract nextToken from response headers
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
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return None, None

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    authToken = get_secret()
    if not authToken:
        print("[ERROR] Failed to retrieve API key from Secrets Manager.")
        return {"statusCode": 500, "body": "API Key retrieval failed"}

    deviceList = []
    nextToken = None

    while True:
        devices, nextToken = merakiAPI(authToken, nextToken)
        if devices is None:
            print("[ERROR] API returned no data. Exiting loop.")
            break

        for device in devices:
            deviceList.append({
                "device_name": device.get("name"),
                "model": device.get("model"),
                "serial": device.get("serial"),
                "firmware": device.get("firmware"),
            })

        # Exit loop if there's no nextToken (last page reached)
        if not nextToken:
            print("[INFO] No more devices to fetch. Exiting loop.")
            break

    # Convert the device list to JSON
    json_data = json.dumps(deviceList, indent=4)

    # Define S3 file details
    current_time = datetime.now()
    filename = f"device_list_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    bucket_name = "eu-central1-dev-uk-snowfall-landing-295446674139"  # Bucket Name
    s3_key = f"meraki/{filename}"

    # Upload JSON data to S3
    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(Body=json_data, Bucket=bucket_name, Key=s3_key)
        print(f"[SUCCESS] Data uploaded to s3://{bucket_name}/{s3_key}")
        return {"statusCode": 200, "body": f"Data uploaded to {s3_key}"}  # ✅ Fixed return statement

    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"[ERROR] Failed to upload data to S3: {e}")
        if error_code == "AccessDenied":
            print("[ERROR] Ensure the Lambda role has PutObject permissions for the S3 bucket.")
        return {"statusCode": 500, "body": "S3 upload failed"}  # ✅ Fixed return statement
