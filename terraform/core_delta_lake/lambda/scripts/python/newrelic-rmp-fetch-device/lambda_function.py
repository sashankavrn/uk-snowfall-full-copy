import requests
import json
import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Details (from environment variable)
S3_BUCKET = os.environ.get("TARGET_BUCKET")
S3_PREFIX = "newrelic/newrelic_rmp_device_info/"

def notify_failure(message):
    """Send SNS notification for a failure event."""
    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        print("[ERROR] SNS_TOPIC_ARN not set in environment variables.")
        return
    try:
        sns_client = boto3.client("sns")
        sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject="newrelic-rmp-device-info-lambda-failure"
        )
        print("[INFO] SNS notification sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

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
            error_message = "[ERROR] Missing API key or account ID in Secrets Manager."
            print(error_message)
            notify_failure(error_message)
            return None, None

        return api_key, account_id

    except Exception as e:
        error_message = f"[ERROR] Failed to retrieve secrets: {e}"
        print(error_message)
        notify_failure(error_message)
        return None, None

# Function to Fetch Data from New Relic API
def new_relic_query(api_key, account_id, nrql):
    """Send an NRQL query to New Relic GraphQL API."""
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    query = "{actor {account(id: " + account_id + ") {nrql(query: \"" + nrql + "\" timeout: 60) {results}}}}"
    try:
        response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})
    except Exception as e:
        error_message = f"[ERROR] Exception during New Relic query: {e}"
        print(error_message)
        notify_failure(error_message)
        return None

    if response.status_code == 200:
        return response.json()
    else:
        error_message = f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}"
        print(error_message)
        notify_failure(error_message)
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
            "sys_updated_timestamp": datetime.now(ZoneInfo("Europe/London")).isoformat()
        }
        for entry in raw_data
    ]
    return processed_data

# Save Data to S3 with Timestamped Filename
def save_to_s3(data):
    """Save JSON data to S3 with a timestamped filename."""
    if not S3_BUCKET:
        error_message = "[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set."
        print(error_message)
        notify_failure(error_message)
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.now(ZoneInfo("Europe/London")).strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_rmp_device_info_{timestamp}.json"

    data_to_write = json.dumps(data, indent=4)

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=data_to_write,
            ContentType="application/json"
        )
        success_message = f"[SUCCESS] JSON data uploaded to s3://{S3_BUCKET}/{s3_key}"
        print(success_message)
        return f"s3://{S3_BUCKET}/{s3_key}"
    except Exception as e:
        error_message = f"[ERROR] Failed to upload JSON data to S3: {e}"
        print(error_message)
        notify_failure(error_message)
        return None

# Lambda Function Handler
def lambda_handler(event, context):
    """AWS Lambda function entry point."""
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()

    if not api_key or not account_id:
        error_message = "[ERROR] Missing API credentials. Aborting process."
        notify_failure(error_message)
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}

    print(f"[INFO] Using New Relic Account ID: {account_id}")

    # Fetch all available hostname prefixes
    print("[INFO] Fetching available hostname prefixes from New Relic...")
    query = "SELECT uniques(substring(hostname,0,7),10000) as 'HostnamePrefix' FROM SystemSample SINCE 1 day ago"
    data = new_relic_query(api_key, account_id, query)

    if not data:
        error_message = "[ERROR] Failed to retrieve hostname prefixes from New Relic."
        notify_failure(error_message)
        return {"statusCode": 500, "body": "Failed to retrieve hostname prefixes from New Relic."}

    try:
        stores = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [0])[0]['HostnamePrefix']
    except Exception as e:
        error_message = f"[ERROR] Unexpected response structure when retrieving hostname prefixes: {e}"
        print(error_message)
        notify_failure(error_message)
        return {"statusCode": 500, "body": "Unexpected response structure for hostname prefixes."}

    if not stores:
        error_message = "[WARNING] No hostname prefixes returned from New Relic."
        print(error_message)
        notify_failure(error_message)
        return {"statusCode": 500, "body": "No hostname prefixes available from New Relic."}
    
    print(f"[INFO] Got {len(stores)} hostname prefixes from New Relic.")

    # Prepare queries for New Relic API
    queries = []
    maxStoresPerRun = 100
    index = 0

    while index < len(stores):
        where_condition = ",".join([f"'{stores[i]}'" for i in range(index, min(index + maxStoresPerRun, len(stores)))])
        # Updated query with new facet logic using displayName over hostname
        query = (
            f"SELECT latest(instanceType), latest(kernelVersion), latest(linuxDistribution), "
            f"latest(operatingSystem), latest(windowsFamily), latest(windowsPlatform), latest(windowsVersion) "
            f"FROM SystemSample WHERE substring(hostname,0,7) in ({where_condition}) SINCE 1 day ago "
            f"FACET if(displayName IS NULL OR displayName = '', hostname, displayName) as 'hostname' LIMIT MAX"
        )
        queries.append(query)
        index += maxStoresPerRun

    raw_data = []

    # Run queries on New Relic API
    print("[INFO] Fetching New Relic data...")
    for query in queries:
        data = new_relic_query(api_key, account_id, query)
        if not data:
            error_message = f"[ERROR] Query returned None for query: {query}"
            print(error_message)
            notify_failure(error_message)
            continue

        # Check for the expected nested structure
        data_level = data.get("data")
        if data_level is None:
            error_message = f"[ERROR] 'data' key missing in response for query: {query}"
            print(error_message)
            notify_failure(error_message)
            continue

        actor = data_level.get("actor")
        if actor is None:
            error_message = f"[ERROR] 'actor' key missing in response for query: {query}"
            print(error_message)
            notify_failure(error_message)
            continue

        account = actor.get("account")
        if account is None:
            error_message = f"[ERROR] 'account' key missing in response for query: {query}"
            print(error_message)
            notify_failure(error_message)
            continue

        nrql = account.get("nrql")
        if nrql is None:
            error_message = f"[ERROR] 'nrql' key missing in response for query: {query}"
            print(error_message)
            notify_failure(error_message)
            continue

        results = nrql.get("results", [])
        raw_data.extend(results)

    if not raw_data:
        error_message = "[WARNING] No data fetched from New Relic."
        print(error_message)
        notify_failure(error_message)
        return {"statusCode": 500, "body": "No data fetched from New Relic."}
    
    print("[INFO] Processing data...")
    processed_data = process_data(raw_data)

    print("[INFO] Saving to S3...")
    s3_url = save_to_s3(processed_data)

    if not s3_url:
        error_message = "[ERROR] Failed to save data to S3."
        notify_failure(error_message)
        return {"statusCode": 500, "body": "Failed to save data to S3."}

    return {
        "statusCode": 200,
        "body": f"Processed data saved to {s3_url}"
    }
