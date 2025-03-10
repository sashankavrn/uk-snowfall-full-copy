import requests
import json
import boto3
import os
from datetime import datetime

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Details (from environment variable)
S3_BUCKET = os.environ.get("TARGET_BUCKET")
S3_PREFIX = "newrelic_digital_response/"

# Function to Fetch Secrets from AWS Secrets Manager
def get_secret():
    """Retrieve API key and account ID from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        return secret["uk-snowfall-newrelic-api-key"], secret["uk-snowfall-newrelic-account-id-digital"]
    except Exception as e:
        print(f"[ERROR] Failed to retrieve secrets: {e}")
        return None, None

# Generate NRQL Query for Digital Response Data
def generate_nrql_query(account_id):
    """Generate NRQL query for retrieving Digital Response Data with explicit date range."""
    since_date = "2025-03-06 00:00:00"
    until_date = "2025-03-07 00:00:00"

    query = f"""
    {{
      actor {{
        account(id: {account_id}) {{
          nrql(
            query: "SELECT uniqueCount(substring(aparse(message, '%ORDER * :%'), 1, 36)) as 'Count' 
            FROM Log 
            WHERE market = 'uk' 
            AND message LIKE '%UpdateOrderStateAsync : MARKET UK : ORDER%' 
            AND (message LIKE '%UpdateOrderStatusAsync%' OR message LIKE '%DoFoeStoreStaging%') 
            FACET aparse(message, '%DoFoeStoreStaging : * :%'), 
            if(length(aparse(message, '%FAULT : * :%')) > 0, aparse(message, '%FAULT : *'), 'No Fault') 
            SINCE '{since_date}' UNTIL '{until_date}' LIMIT MAX"
            timeout: 60
          ) {{
            results
          }}
        }}
      }}
    }}
    """
    return query

# Fetch Data from New Relic API
def fetch_newrelic_data(api_key, account_id):
    """Fetch NRQL query results from New Relic GraphQL API."""
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }

    query = generate_nrql_query(account_id)
    response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})

    if response.status_code == 200:
        data = response.json()
        results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
        return results
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

# Process and Structure Data
def process_data(raw_data):
    """Extract restaurant number, fault details, and count from API response."""
    processed_data = [
        {
            "Restaurant Number": entry["facet"][0],  # Extract restaurant number
            "Fault": entry["facet"][1],  # Extract fault details
            "Count": entry["Count"],  # Extract count
            "sys_updated_timestamp": datetime.utcnow().isoformat()
        }
        for entry in raw_data
    ]
    return processed_data

# Save Data to S3 with Timestamped Filename
def save_to_s3(data):
    """Save JSON data to a new timestamped file in S3."""
    if not S3_BUCKET:
        print("[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set.")
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_digital_responses_{timestamp}.json"

    data_to_write = data if data else [{"message": "No data found from New Relic"}]

    try:
        response = s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data_to_write, indent=4),
            ContentType="application/json"
        )
        print(f"[SUCCESS] Data uploaded to s3://{S3_BUCKET}/{s3_key}")
        return s3_key

    except Exception as e:
        print(f"[ERROR] Failed to upload data to S3: {e}")
        return None

# Lambda Function Handler
def lambda_handler(event, context):
    """AWS Lambda function entry point."""
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()
    
    if not api_key or not account_id:
        print("[ERROR] Missing API credentials. Aborting process.")
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}

    print("[INFO] Fetching New Relic data...")
    raw_data = fetch_newrelic_data(api_key, account_id)
    
    if not raw_data:
        print("[WARNING] No data fetched from New Relic, writing an empty file.")
    
    print("[INFO] Processing data...")
    processed_data = process_data(raw_data)

    print("[INFO] Saving to S3...")
    s3_key = save_to_s3(processed_data)

    return {"statusCode": 200, "body": f"Processed data saved to S3: {s3_key}"}
