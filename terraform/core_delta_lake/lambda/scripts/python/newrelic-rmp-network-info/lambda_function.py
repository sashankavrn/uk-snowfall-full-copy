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
TARGET_BUCKET    = os.environ.get("TARGET_BUCKET")

# S3 key prefix for network info data
S3_PREFIX = "newrelic/newrelic_rmp_network_info/"

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
            Subject="newrelic-rmp-network-info-lambda-failure"
        )
        print("[INFO] SNS notification sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

def get_secret():
    """Retrieve API key and account ID from AWS Secrets Manager."""
    session = boto3.session.Session()
    client  = session.client(service_name="secretsmanager", region_name=REGION_NAME)
    try:
        resp   = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(resp["SecretString"])
        api_key    = secret.get("uk-snowfall-newrelic-api-key")
        account_id = secret.get("uk-snowfall-newrelic-account-id-rmp")
        if not api_key or not account_id:
            msg = "[ERROR] Missing API key or account ID in Secrets Manager."
            print(msg)
            notify_failure(msg)
            return None, None
        return api_key, str(account_id)
    except Exception as e:
        msg = f"[ERROR] Failed to retrieve secrets: {e}"
        print(msg)
        notify_failure(msg)
        return None, None

def new_relic_query(api_key, account_id, nrql):
    """Send an NRQL query to the New Relic GraphQL API."""
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key":    api_key
    }
    payload = {
        "query": f'{{actor {{account(id: {account_id}) {{nrql(query: "{nrql}", timeout: 60) {{results}}}}}}}}'
    }
    resp = requests.post("https://api.newrelic.com/graphql", headers=headers, json=payload)
    if resp.status_code == 200:
        return resp.json()
    else:
        msg = f"[ERROR] Failed to fetch data: {resp.status_code}, {resp.text}"
        print(msg)
        notify_failure(msg)
        return None

def process_data(raw_data):
    """
    Process raw network data from New Relic into a structured list.
    Removed logic extracting restaurant_number and device from hostname.
    """
    processed = []
    for entry in raw_data:
        processed.append({
            "hostname":                          entry.get("hostname"),
            "latest_hardwareAddress":            entry.get("latest.hardwareAddress"),
            "latest_interfaceName":              entry.get("latest.interfaceName"),
            "latest_ipV4Address":                entry.get("latest.ipV4Address"),
            "latest_ipV6Address":                entry.get("latest.ipV6Address"),
            "average_receiveBytesPerSecond":     entry.get("average.receiveBytesPerSecond"),
            "average_receiveDroppedPerSecond":   entry.get("average.receiveDroppedPerSecond"),
            "average_receiveErrorsPerSecond":    entry.get("average.receiveErrorsPerSecond"),
            "average_receivePacketsPerSecond":   entry.get("average.receivePacketsPerSecond"),
            "average_transmitBytesPerSecond":    entry.get("average.transmitBytesPerSecond"),
            "average_transmitDroppedPerSecond":  entry.get("average.transmitDroppedPerSecond"),
            "average_transmitErrorsPerSecond":   entry.get("average.transmitErrorsPerSecond"),
            "average_transmitPacketsPerSecond":  entry.get("average.transmitPacketsPerSecond"),
            "sys_updated_timestamp":             datetime.now().isoformat()
        })
    return processed

def save_to_bucket(bucket, prefix, data):
    """Save JSON data to S3 with a timestamped filename."""
    if not bucket:
        msg = "[ERROR] Bucket is not set."
        print(msg)
        notify_failure(msg)
        return None
    s3      = boto3.client("s3")
    ts      = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key  = f"{prefix}newrelic_rmp_network_info_{ts}.json"
    payload = json.dumps(data, indent=4)
    try:
        s3.put_object(
            Bucket      = bucket,
            Key         = s3_key,
            Body        = payload,
            ContentType = "application/json"
        )
        url = f"s3://{bucket}/{s3_key}"
        print(f"[SUCCESS] JSON data uploaded to {url}")
        return url
    except Exception as e:
        msg = f"[ERROR] Failed to upload JSON data to bucket {bucket}: {e}"
        print(msg)
        notify_failure(msg)
        return None

def lambda_handler(event, context):
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()
    if not api_key or not account_id:
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}

    print(f"[INFO] Using New Relic Account ID: {account_id}")

    # Step 1: fetch unique hostname prefixes over 1 day
    prefix_query = (
        "SELECT uniques(substring(hostname,0,7), 10000) "
        "as 'HostnamePrefix' FROM NetworkSample SINCE 1 day ago"
    )
    print("[INFO] Fetching hostname prefixes from New Relic...")
    prefix_data = new_relic_query(api_key, account_id, prefix_query)
    if not prefix_data:
        return {"statusCode": 500, "body": "Failed to retrieve hostname prefixes."}

    prefix_results = (
        prefix_data.get("data", {})
                   .get("actor", {})
                   .get("account", {})
                   .get("nrql", {})
                   .get("results", [])
    )
    if not prefix_results:
        msg = "No hostname prefixes available."
        print(f"[WARNING] {msg}")
        notify_failure(msg)
        return {"statusCode": 500, "body": msg}

    stores = prefix_results[0].get("HostnamePrefix", [])
    print(f"[INFO] Retrieved {len(stores)} prefixes.")

    # Step 2: batch prefixes into detailed NRQL queries
    max_per_batch = 100
    queries       = []
    index         = 0
    while index < len(stores):
        batch  = stores[index : index + max_per_batch]
        quoted = ",".join(f"'{p}'" for p in batch)
        queries.append(
            "SELECT latest(hardwareAddress), latest(interfaceName), "
            "latest(ipV4Address), latest(ipV6Address), "
            "average(receiveBytesPerSecond), average(receiveDroppedPerSecond), "
            "average(receiveErrorsPerSecond), average(receivePacketsPerSecond), "
            "average(transmitBytesPerSecond), average(transmitDroppedPerSecond), "
            "average(transmitErrorsPerSecond), average(transmitPacketsPerSecond) "
            "FROM NetworkSample SINCE 10 minutes ago "
            f"WHERE substring(hostname,0,7) in ({quoted}) "
            "FACET if(displayName IS NULL OR displayName = '', hostname, displayName) as 'hostname' "
            "LIMIT MAX"
        )
        index += max_per_batch

    # Step 3: execute detailed queries
    raw_data = []
    print(f"[INFO] Running {len(queries)} detailed queries...")
    for q in queries:
        result = new_relic_query(api_key, account_id, q)
        if result:
            rows = (
                result.get("data", {})
                      .get("actor", {})
                      .get("account", {})
                      .get("nrql", {})
                      .get("results", [])
            )
            raw_data.extend(rows)
    print(f"[INFO] Retrieved detailed metrics for {len(raw_data)} hosts.")

    # Step 4: process and save
    processed    = process_data(raw_data)
    url_target   = save_to_bucket(TARGET_BUCKET,    S3_PREFIX, processed)
    url_datashare= save_to_bucket(DATASHARE_BUCKET, S3_PREFIX, processed)

    if url_target and url_datashare:
        return {
            "statusCode": 200,
            "body": f"Processed data saved to TARGET_BUCKET: {url_target} and DATASHARE_BUCKET: {url_datashare}"
        }
    else:
        msg = "Failed to save data to one or both buckets."
        notify_failure(msg)
        return {"statusCode": 500, "body": msg}
