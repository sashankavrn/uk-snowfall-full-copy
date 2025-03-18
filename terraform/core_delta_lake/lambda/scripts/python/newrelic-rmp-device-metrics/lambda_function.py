import requests
import json
import boto3
import os
from datetime import datetime

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Bucket Details (from environment variables)
DATASHARE_BUCKET = os.environ.get("DATASHARE_BUCKET")
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")
# Updated S3 key prefix
S3_PREFIX = "newrelic_rmp_device_metrics/"

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
    query = (
        "{actor {account(id: " + account_id + ") {nrql(query: \"" + nrql + "\" timeout: 60) {results}}}}"
    )
    response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

# Process and Structure Data
def process_data(raw_data):
    """
    Extract hostname and relevant fields from API response into a single dataset.
    Expected raw_data is a list of dictionaries where each dictionary represents data for a hostname.
    """
    processed_data = []
    for entry in raw_data:
        processed_entry = {
            "hostname": entry.get("hostname"),
            "coreCount": entry.get("latest.coreCount"),
            "processorCount": entry.get("latest.processorCount"),
            "cpuIOWaitPercent": entry.get("average.cpuIOWaitPercent"),
            "cpuIdlePercent": entry.get("average.cpuIdlePercent"),
            "cpuPercent": entry.get("average.cpuPercent"),
            "cpuStealPercent": entry.get("average.cpuStealPercent"),
            "cpuSystemPercent": entry.get("average.cpuSystemPercent"),
            "cpuUserPercent": entry.get("average.cpuUserPercent"),
            "diskFreeBytes": entry.get("average.diskFreeBytes"),
            "diskFreePercent": entry.get("average.diskFreePercent"),
            "diskReadUtilizationPercent": entry.get("average.diskReadUtilizationPercent"),
            "diskReadsPerSecond": entry.get("average.diskReadsPerSecond"),
            "diskTotalBytes": entry.get("average.diskTotalBytes"),
            "diskUsedBytes": entry.get("average.diskUsedBytes"),
            "diskUsedPercent": entry.get("average.diskUsedPercent"),
            "diskUtilizationPercent": entry.get("average.diskUtilizationPercent"),
            "diskWriteUtilizationPercent": entry.get("average.diskWriteUtilizationPercent"),
            "diskWritesPerSecond": entry.get("average.diskWritesPerSecond"),
            "loadAverageFifteenMinute": entry.get("average.loadAverageFifteenMinute"),
            "loadAverageFiveMinute": entry.get("average.loadAverageFiveMinute"),
            "loadAverageOneMinute": entry.get("average.loadAverageOneMinute"),
            "memoryCachedBytes": entry.get("average.memoryCachedBytes"),
            "memoryFreeBytes": entry.get("average.memoryFreeBytes"),
            "memoryFreePercent": entry.get("average.memoryFreePercent"),
            "memorySharedBytes": entry.get("average.memorySharedBytes"),
            "memorySlabBytes": entry.get("average.memorySlabBytes"),
            "memoryTotalBytes": entry.get("average.memoryTotalBytes"),
            "memoryUsedBytes": entry.get("average.memoryUsedBytes"),
            "memoryUsedPercent": entry.get("average.memoryUsedPercent"),
            "swapFreeBytes": entry.get("average.swapFreeBytes"),
            "swapTotalBytes": entry.get("average.swapTotalBytes"),
            "swapUsedBytes": entry.get("average.swapUsedBytes"),
            "systemMemoryBytes": entry.get("latest.systemMemoryBytes"),
            "sys_updated_timestamp": datetime.utcnow().isoformat()
        }
        processed_data.append(processed_entry)
    return processed_data

# Function to Save Data to a Specified Bucket with the new S3 key prefix and filename
def save_to_bucket(bucket, prefix, data):
    """Save JSON data to a specified S3 bucket with a timestamped filename using the provided prefix."""
    if not bucket:
        print("[ERROR] Bucket is not set.")
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    # Updated filename format
    s3_key = f"{prefix}newrelic_rmp_device_metrics_{timestamp}.json"
    data_to_write = json.dumps(data, indent=4)
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=data_to_write,
            ContentType="application/json"
        )
        print(f"[SUCCESS] JSON data uploaded to s3://{bucket}/{s3_key}")
        return f"s3://{bucket}/{s3_key}"
    except Exception as e:
        print(f"[ERROR] Failed to upload JSON data to bucket {bucket}: {e}")
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

    # New NRQL query for detailed system metrics
    query = (
        "SELECT latest(coreCount), latest(processorCount), average(cpuIOWaitPercent), average(cpuIdlePercent), "
        "average(cpuPercent), average(cpuStealPercent), average(cpuSystemPercent), average(cpuUserPercent), "
        "average(diskFreeBytes), average(diskFreePercent), average(diskReadUtilizationPercent), average(diskReadsPerSecond), "
        "average(diskTotalBytes), average(diskUsedBytes), average(diskUsedPercent), average(diskUtilizationPercent), "
        "average(diskWriteUtilizationPercent), average(diskWritesPerSecond), average(loadAverageFifteenMinute), "
        "average(loadAverageFiveMinute), average(loadAverageOneMinute), average(memoryCachedBytes), average(memoryFreeBytes), "
        "average(memoryFreePercent), average(memorySharedBytes), average(memorySlabBytes), average(memoryTotalBytes), "
        "average(memoryUsedBytes), average(memoryUsedPercent), average(swapFreeBytes), average(swapTotalBytes), "
        "average(swapUsedBytes), latest(systemMemoryBytes) FROM SystemSample SINCE 2 minutes ago FACET hostname LIMIT MAX"
    )

    print("[INFO] Fetching New Relic data...")
    data = new_relic_query(api_key, account_id, query)
    if not data:
        print("[ERROR] Failed to retrieve data from New Relic.")
        return {"statusCode": 500, "body": "Failed to retrieve data from New Relic."}

    raw_data = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    if not raw_data:
        print("[WARNING] No data fetched from New Relic.")
        return {"statusCode": 500, "body": "No data fetched from New Relic."}

    print(f"[INFO] Fetched data for {len(raw_data)} hostnames.")
    print("[INFO] Processing data...")
    processed_data = process_data(raw_data)

    print("[INFO] Saving data to TARGET_BUCKET...")
    target_s3_url = save_to_bucket(TARGET_BUCKET, S3_PREFIX, processed_data)

    print("[INFO] Saving data to DATASHARE_BUCKET...")
    datashare_s3_url = save_to_bucket(DATASHARE_BUCKET, S3_PREFIX, processed_data)

    return {
        "statusCode": 200,
        "body": f"Processed data saved to TARGET_BUCKET: {target_s3_url} and DATASHARE_BUCKET: {datashare_s3_url}"
        if target_s3_url and datashare_s3_url
        else "Failed to save data to one or both buckets."
    }
