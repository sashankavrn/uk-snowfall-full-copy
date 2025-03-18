import requests
import json
import boto3
import os
from datetime import datetime

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Details (from environment variable)
S3_BUCKET = os.environ.get("TARGET_BUCKET")  # Get bucket from Lambda environment variable
S3_PREFIX = "newrelic/newrelic_digital_response/"  # Folder in S3 bucket

# Function to Fetch Secrets from AWS Secrets Manager
def get_secret():
    """Retrieve API key and account ID from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        api_key = secret.get("uk-snowfall-newrelic-api-key")
        account_id = secret.get("uk-snowfall-newrelic-account-id-digital")

        if not api_key or not account_id:
            print("[ERROR] Missing API key or account ID in Secrets Manager.")
            return None, None

        return api_key, int(account_id)  # ✅ Ensure account ID is an integer

    except Exception as e:
        print(f"[ERROR] Failed to retrieve secrets: {e}")
        return None, None

# Function to Fetch Data from New Relic API
def new_relic_query(api_key, account_id, nrql):
    """Send an NRQL query to New Relic GraphQL API."""
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }

    query_payload = json.dumps({
        "query": f"""
        {{
          actor {{
            account(id: {account_id}) {{  # ✅ Fix: Account ID as integer
              nrql(query: \"""
              {nrql}
              \""", timeout: 60) {{
                results
              }}
            }}
          }}
        }}
        """
    })

    print("[DEBUG] Sending query to New Relic:", query_payload)  # ✅ Debugging NRQL Query

    response = requests.post("https://api.newrelic.com/graphql", headers=headers, data=query_payload)

    if response.status_code == 200:
        response_json = response.json()
        print("[DEBUG] New Relic Response:", json.dumps(response_json, indent=2))  # ✅ Print Response
        return response_json
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

# Save Data to S3 with Timestamped Filename
def save_to_s3(data):
    """Save JSON data to S3 with a timestamped filename."""
    
    if not S3_BUCKET:
        print("[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set.")
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_digital_response_{timestamp}.json"

    data_to_write = json.dumps(data, indent=4)

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=data_to_write,
            ContentType="application/json"
        )
        print(f"[SUCCESS] JSON data uploaded to s3://{S3_BUCKET}/{s3_key}")
        return f"s3://{S3_BUCKET}/{s3_key}"

    except Exception as e:
        print(f"[ERROR] Failed to upload JSON data to S3: {e}")
        return None

# Lambda Function Handler
def lambda_handler(event, context):
    """AWS Lambda function entry point."""
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()

    if not api_key or not account_id:
        print("[ERROR] Missing API credentials. Aborting process.")
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}

    print(f"[INFO] Using New Relic Account ID: {account_id}")

    # New NRQL query for digital response log data
    query = """
        SELECT uniqueCount(substring(aparse(message, '%ORDER * :%'), 1, 36)) as 'Count' 
        FROM Log 
        WHERE market = 'uk' 
        AND message LIKE '%UpdateOrderStateAsync : MARKET UK : ORDER%' 
        AND (message LIKE '%UpdateOrderStatusAsync%' OR message LIKE '%DoFoeStoreStaging%') 
        FACET aparse(message, '%DoFoeStoreStaging : * :%'),  
        if(length(aparse(message, '%FAULT : * :%')) > 0, aparse(message, '%FAULT : *'), 'No Fault') 
        SINCE 3 days ago 
        LIMIT MAX
    """
    
    print("[INFO] Fetching New Relic digital response data...")
    data = new_relic_query(api_key, account_id, query)

    if not data:
        print("[ERROR] Failed to retrieve log data from New Relic.")
        return {"statusCode": 500, "body": "Failed to retrieve digital response log data from New Relic."}

    results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    
    if not results:
        print("[WARNING] No digital response log data returned from New Relic.")
        return {"statusCode": 500, "body": "No digital response log data available from New Relic."}
    
    print(f"[INFO] Retrieved {len(results)} digital response log entries from New Relic.")

    print("[INFO] Saving to S3...")
    s3_url = save_to_s3(results)

    return {
        "statusCode": 200,
        "body": f"Processed data saved to {s3_url}" if s3_url else "Failed to save data to S3."
    }
