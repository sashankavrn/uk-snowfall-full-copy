import requests
import json
import boto3
import os
from datetime import datetime
import re

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Bucket Details (from environment variables)
DATASHARE_BUCKET = os.environ.get("DATASHARE_BUCKET")
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")
# S3 key prefix for metrics data
S3_PREFIX = "newrelic/newrelic_rmp_device_metrics/"

def get_secret():
    """Retrieve API key and account ID from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        api_key = secret.get("uk-snowfall-newrelic-api-key")
        account_id = secret.get("uk-snowfall-newrelic-account-id-rmp")
        if not api_key or not account_id:
            print("[ERROR] Missing API key or account ID in Secrets Manager.")
            return None, None
        return api_key, str(account_id)
    except Exception as e:
        print(f"[ERROR] Failed to retrieve secrets: {e}")
        return None, None

def new_relic_query(api_key, account_id, nrql):
    """Send an NRQL query to the New Relic GraphQL API."""
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    query = f'{{actor {{account(id: {account_id}) {{nrql(query: "{nrql}", timeout: 60) {{results}}}}}}}}'
    response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

def process_data(raw_data):
    """
    Process raw metric data from New Relic into a structured list.
    Each entry is expected to contain fields for a hostname.
    Additionally, this function derives:
      - restaurant_number: integer derived from numeric digits found in hostname substring (indexes 2-7)
      - device: last 5 characters of the hostname
    """
    processed_data = []
    for entry in raw_data:
        hostname = entry.get("hostname")
        restaurant_number = None
        device = None
        if hostname and len(hostname) >= 7:
            # Attempt to extract digits from the substring (indexes 2 to 7)
            substring = hostname[2:7]
            match = re.search(r'\d+', substring)
            if match:
                try:
                    restaurant_number = int(match.group())
                except Exception as e:
                    print(f"[WARNING] Failed to convert extracted digits from hostname {hostname}: {e}")
            else:
                # Optional: Try to extract digits from the entire hostname if desired
                match = re.search(r'\d+', hostname)
                if match:
                    try:
                        restaurant_number = int(match.group())
                    except Exception as e:
                        print(f"[WARNING] Failed to convert digits from hostname {hostname}: {e}")
            # Get last 5 characters as device if hostname is long enough
            if len(hostname) >= 5:
                device = hostname[-5:]
        
        processed_entry = {
            "hostname": hostname,
            "restaurant_number": restaurant_number,
            "device": device,
            "latest_coreCount": entry.get("latest.coreCount"),
            "latest_processorCount": entry.get("latest.processorCount"),
            "average_cpuIOWaitPercent": entry.get("average.cpuIOWaitPercent"),
            "average_cpuIdlePercent": entry.get("average.cpuIdlePercent"),
            "average_cpuPercent": entry.get("average.cpuPercent"),
            "average_cpuStealPercent": entry.get("average.cpuStealPercent"),
            "average_cpuSystemPercent": entry.get("average.cpuSystemPercent"),
            "average_cpuUserPercent": entry.get("average.cpuUserPercent"),
            "average_diskFreeBytes": entry.get("average.diskFreeBytes"),
            "average_diskFreePercent": entry.get("average.diskFreePercent"),
            "average_diskReadUtilizationPercent": entry.get("average.diskReadUtilizationPercent"),
            "average_diskReadsPerSecond": entry.get("average.diskReadsPerSecond"),
            "average_diskTotalBytes": entry.get("average.diskTotalBytes"),
            "average_diskUsedBytes": entry.get("average.diskUsedBytes"),
            "average_diskUsedPercent": entry.get("average.diskUsedPercent"),
            "average_diskUtilizationPercent": entry.get("average.diskUtilizationPercent"),
            "average_diskWriteUtilizationPercent": entry.get("average.diskWriteUtilizationPercent"),
            "average_diskWritesPerSecond": entry.get("average.diskWritesPerSecond"),
            "average_loadAverageFifteenMinute": entry.get("average.loadAverageFifteenMinute"),
            "average_loadAverageFiveMinute": entry.get("average.loadAverageFiveMinute"),
            "average_loadAverageOneMinute": entry.get("average.loadAverageOneMinute"),
            "average_memoryCachedBytes": entry.get("average.memoryCachedBytes"),
            "average_memoryFreeBytes": entry.get("average.memoryFreeBytes"),
            "average_memoryFreePercent": entry.get("average.memoryFreePercent"),
            "average_memorySharedBytes": entry.get("average.memorySharedBytes"),
            "average_memorySlabBytes": entry.get("average.memorySlabBytes"),
            "average_memoryTotalBytes": entry.get("average.memoryTotalBytes"),
            "average_memoryUsedBytes": entry.get("average.memoryUsedBytes"),
            "average_memoryUsedPercent": entry.get("average.memoryUsedPercent"),
            "average_swapFreeBytes": entry.get("average.swapFreeBytes"),
            "average_swapTotalBytes": entry.get("average.swapTotalBytes"),
            "average_swapUsedBytes": entry.get("average.swapUsedBytes"),
            "latest_systemMemoryBytes": entry.get("latest.systemMemoryBytes"),
            "sys_updated_timestamp": datetime.utcnow().isoformat()
        }
        processed_data.append(processed_entry)
    return processed_data

def save_to_bucket(bucket, prefix, data):
    """Save JSON data to the specified S3 bucket with a timestamped filename."""
    if not bucket:
        print("[ERROR] Bucket is not set.")
        return None
    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
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

def lambda_handler(event, context):
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()
    if not api_key or not account_id:
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}
    print(f"[INFO] Using New Relic Account ID: {account_id}")

    # Step 1: Fetch unique hostname prefixes over 1 day
    prefix_query = "SELECT uniques(substring(hostname,0,7), 10000) as 'HostnamePrefix' FROM SystemSample SINCE 1 day ago"
    print("[INFO] Fetching unique hostname prefixes from New Relic...")
    prefix_data = new_relic_query(api_key, account_id, prefix_query)
    if not prefix_data:
        print("[ERROR] Prefix query returned no data.")
        return {"statusCode": 500, "body": "Failed to retrieve hostname prefixes from New Relic."}
    
    print("[DEBUG] Prefix data response:", json.dumps(prefix_data))
    
    prefix_results = prefix_data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    if not prefix_results or len(prefix_results) == 0:
        print("[WARNING] No hostname prefix results returned from New Relic.")
        return {"statusCode": 500, "body": "No hostname prefixes available from New Relic."}
    
    stores = prefix_results[0].get("HostnamePrefix", [])
    if not stores:
        print("[WARNING] The 'HostnamePrefix' key is missing or empty in the results.")
        return {"statusCode": 500, "body": "No hostname prefixes available from New Relic."}
    
    print(f"[INFO] Retrieved {len(stores)} hostname prefixes.")

    # Step 2: Batch these prefixes and run detailed queries for metrics
    maxPrefixesPerBatch = 100
    queries = []
    index = 0
    while index < len(stores):
        batch = stores[index : index + maxPrefixesPerBatch]
        quoted = ",".join([f"'{prefix}'" for prefix in batch])
        # Updated query with new facet logic using displayName over hostname
        detailed_query = (
            "SELECT latest(coreCount), latest(processorCount), average(cpuIOWaitPercent), average(cpuIdlePercent), "
            "average(cpuPercent), average(cpuStealPercent), average(cpuSystemPercent), average(cpuUserPercent), "
            "average(diskFreeBytes), average(diskFreePercent), average(diskReadUtilizationPercent), average(diskReadsPerSecond), "
            "average(diskTotalBytes), average(diskUsedBytes), average(diskUsedPercent), average(diskUtilizationPercent), "
            "average(diskWriteUtilizationPercent), average(diskWritesPerSecond), average(loadAverageFifteenMinute), "
            "average(loadAverageFiveMinute), average(loadAverageOneMinute), average(memoryCachedBytes), average(memoryFreeBytes), "
            "average(memoryFreePercent), average(memorySharedBytes), average(memorySlabBytes), average(memoryTotalBytes), "
            "average(memoryUsedBytes), average(memoryUsedPercent), average(swapFreeBytes), average(swapTotalBytes), "
            "average(swapUsedBytes), latest(systemMemoryBytes) FROM SystemSample SINCE 1 day ago "
            f"WHERE substring(hostname,0,7) in ({quoted}) "
            "FACET if(displayName IS NULL OR displayName = '', hostname, displayName) as 'hostname' LIMIT MAX"
        )
        queries.append(detailed_query)
        index += maxPrefixesPerBatch

    raw_data = []
    print(f"[INFO] Running detailed queries in {len(queries)} batches...")
    for q in queries:
        result = new_relic_query(api_key, account_id, q)
        if result:
            results = result.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
            raw_data.extend(results)
    print(f"[INFO] Retrieved detailed metrics for {len(raw_data)} hostnames.")

    processed_data = process_data(raw_data)
    print("[INFO] Saving data to TARGET_BUCKET...")
    target_url = save_to_bucket(TARGET_BUCKET, S3_PREFIX, processed_data)
    print("[INFO] Saving data to DATASHARE_BUCKET...")
    datashare_url = save_to_bucket(DATASHARE_BUCKET, S3_PREFIX, processed_data)

    return {
        "statusCode": 200,
        "body": f"Processed data saved to TARGET_BUCKET: {target_url} and DATASHARE_BUCKET: {datashare_url}"
        if target_url and datashare_url
        else "Failed to save data to one or both buckets."
    }

if __name__ == "__main__":
    print(lambda_handler({}, {}))
