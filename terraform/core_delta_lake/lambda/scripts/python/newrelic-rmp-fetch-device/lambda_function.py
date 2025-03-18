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
S3_PREFIX = "newrelic/newrelic_rmp_device/"

# Function to Fetch Secrets from AWS Secrets Manager
def get_secret():
    """Retrieve API key and account ID from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        api_key = secret.get("uk-snowfall-newrelic-api-key")
        account_id = secret.get("uk-snowfall-newrelic-account-id-rmp")  # Fetching account ID dynamically

        if not api_key or not account_id:
            print("[ERROR] Missing API key or account ID in Secrets Manager.")
            return None, None

        return api_key, account_id

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
    query = "{actor {account(id: " + account_id + ") {nrql(query: \"" + nrql + "\" timeout: 60) {results}}}}"

    response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})

    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

# Process and Structure Data
def process_data(raw_data):
    """Extract hostname and relevant fields from API response into a single dataset."""
    processed_data = [
        {
            "hostname": entry.get("hostname"),
            "instanceType": entry.get("latest.instanceType"),
            "kernelVersion": entry.get("latest.kernelVersion"),
            "linuxDistribution": entry.get("latest.linuxDistribution"),
            "operatingSystem": entry.get("latest.operatingSystem"),
            "windowsFamily": entry.get("latest.windowsFamily"),
            "windowsPlatform": entry.get("latest.windowsPlatform"),
            "windowsVersion": entry.get("latest.windowsVersion"),
            "sys_updated_timestamp": datetime.utcnow().isoformat()
        }
        for entry in raw_data
    ]
    return processed_data

# Save Data to S3 with Timestamped Filename
def save_to_s3(data):
    """Save JSON data to S3 with a timestamped filename."""
    
    if not S3_BUCKET:
        print("[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set.")
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_rmp_device_info_{timestamp}.json"

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

    # Fetch all available hostname prefixes
    print("[INFO] Fetching available hostname prefixes from New Relic...")
    query = "SELECT uniques(substring(hostname,0,7),10000) as 'HostnamePrefix' FROM SystemSample SINCE 1 day ago"
    data = new_relic_query(api_key, account_id, query)

    if not data:
        print("[ERROR] Failed to retrieve hostname prefixes from New Relic.")
        return {"statusCode": 500, "body": "Failed to retrieve hostname prefixes from New Relic."}

    stores = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [0])[0]['HostnamePrefix']
    
    if not stores:
        print("[WARNING] No hostname prefixes returned from New Relic.")
        return {"statusCode": 500, "body": "No hostname prefixes available from New Relic."}
    
    print(f"[INFO] Got {len(stores)} hostname prefixes from New Relic.")

    # Prepare queries for New Relic API
    queries = []
    maxStoresPerRun = 100
    index = 0

    while index < len(stores):
        where_condition = ",".join([f"'{stores[i]}'" for i in range(index, min(index + maxStoresPerRun, len(stores)))])
        query = f"SELECT latest(instanceType), latest(kernelVersion), latest(linuxDistribution), latest(operatingSystem), latest(windowsFamily), latest(windowsPlatform), latest(windowsVersion) FROM SystemSample WHERE substring(hostname,0,7) in ({where_condition}) SINCE 1 day ago FACET hostname LIMIT MAX"
        queries.append(query)
        index += maxStoresPerRun

    raw_data = []

    # Run queries on New Relic API
    print("[INFO] Fetching New Relic data...")
    for query in queries:
        data = new_relic_query(api_key, account_id, query)
        if data:
            results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
            raw_data.extend(results)

    if not raw_data:
        print("[WARNING] No data fetched from New Relic.")
        return {"statusCode": 500, "body": "No data fetched from New Relic."}
    
    print("[INFO] Processing data...")
    processed_data = process_data(raw_data)

    print("[INFO] Saving to S3...")
    s3_url = save_to_s3(processed_data)

    return {
        "statusCode": 200,
        "body": f"Processed data saved to {s3_url}" if s3_url else "Failed to save data to S3."
    }
