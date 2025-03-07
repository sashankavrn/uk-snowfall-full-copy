import requests
import json
import boto3
import os
import time
from datetime import datetime, timezone
from botocore.exceptions import BotoCoreError, ClientError

# AWS Secrets Manager fetch function
def get_secret(secret_name):
    """Retrieve secrets from AWS Secrets Manager."""
    region_name = "eu-central-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            return json.loads(response['SecretString'])
        else:
            raise ValueError("SecretString not found in response")
    except (BotoCoreError, ClientError) as e:
        print(f"[ERROR] Failed to retrieve secret {secret_name}: {e}")
        return None

# Function to fetch data from New Relic API
def newrelicAPI(authToken, account_id, retries=3):
    """Fetch system sample data from New Relic GraphQL API."""
    url = "https://api.newrelic.com/graphql"
    
    query = f"""
    {{
      actor {{
        account(id: {account_id}) {{
          nrql(
            query: "SELECT latest(instanceType), latest(kernelVersion), latest(linuxDistribution), latest(operatingSystem), latest(windowsFamily), latest(windowsPlatform), latest(windowsVersion) FROM SystemSample SINCE 24 hours ago FACET hostname limit max"
            timeout: 60
          ) {{
            results
          }}
        }}
      }}
    }}
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": authToken
    }

    payload = json.dumps({"query": query, "variables": ""})

    for attempt in range(retries):
        try:
            print(f"[INFO] Attempt {attempt+1}: Fetching New Relic system data...")
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] API request failed (Attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None

# AWS Lambda handler function
def lambda_handler(event, context):
    """Fetch data from New Relic API and store in S3."""
    
    # Retrieve API Key
    api_secret = get_secret("uk-snowfall-newrelic-api-key")
    if not api_secret:
        print("[ERROR] Failed to retrieve New Relic API Key from Secrets Manager.")
        return {"statusCode": 500, "body": "API Key retrieval failed"}

    authToken = f"Api-Key {api_secret['newrelic-api-key']}"
    
    # Retrieve Account ID
    account_secret = get_secret("uk-snowfall-newrelic-account-id-rmp")
    if not account_secret:
        print("[ERROR] Failed to retrieve New Relic Account ID from Secrets Manager.")
        return {"statusCode": 500, "body": "Account ID retrieval failed"}

    account_id = account_secret["newrelic-account-id"]

    # Fetch device info from New Relic
    data = newrelicAPI(authToken, account_id)
    if data is None:
        print("[ERROR] API returned no data. Exiting.")
        return {"statusCode": 500, "body": "Failed to fetch data from New Relic"}

    # Extract results
    results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])

    if not results:
        print("[WARNING] No device data retrieved.")
        return {"statusCode": 204, "body": "No data available"}

    # Format and add timestamps
    sys_updated_timestamp = datetime.now(timezone.utc).isoformat()
    formatted_data = [
        {**device, "sys_updated_timestamp": sys_updated_timestamp}
        for device in results
    ]

    json_data = json.dumps(formatted_data, indent=4)
    
    # Upload JSON to S3 (WITHOUT OVERWRITING OLD DATA)
    current_time = datetime.now()
    filename = f"newrelic_device_info_{current_time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    bucket_name = os.environ.get('TARGET_BUCKET')
    s3_key = f"newrelic-device-info/{filename}"

    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(Body=json_data, Bucket=bucket_name, Key=s3_key)
        print(f"[SUCCESS] Data uploaded to s3://{bucket_name}/{s3_key}")
        return {"statusCode": 200, "body": f"Data uploaded to {s3_key}"}
    except ClientError as e:
        print(f"[ERROR] Failed to upload data to S3: {e}")
        return {"statusCode": 500, "body": "S3 upload failed"}
