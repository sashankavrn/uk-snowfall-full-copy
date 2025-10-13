import requests
import json
import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Bucket Details (from environment variables)
DATASHARE_BUCKET = os.environ.get("DATASHARE_BUCKET")
TARGET_BUCKET = os.environ.get("TARGET_BUCKET")
S3_PREFIX = "newrelic/newrelic_rmp_process_info/"

def notify_failure(message):
    """Send SNS notification for a failure event with timestamp in subject and body."""
    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        print("[ERROR] SNS_TOPIC_ARN not set in environment variables.")
        return
    try:
        sns_client = boto3.client("sns")
        timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
        full_message = f"{timestamp} - {message}"
        subject_line = f"newrelic-rmp-process-info-lambda-failure @ {timestamp}"
        sns_client.publish(
            TopicArn=topic_arn,
            Message=full_message,
            Subject=subject_line
        )
        print("[INFO] SNS notification sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

def get_secret():
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        api_key = secret.get("uk-snowfall-newrelic-api-key")
        account_id = secret.get("uk-snowfall-newrelic-account-id-rmp")
        if not api_key or not account_id:
            error_message = "[ERROR] Missing API key or account ID in Secrets Manager."
            print(error_message)
            notify_failure(error_message)
            return None, None
        return api_key, str(account_id)
    except Exception as e:
        error_message = f"[ERROR] Failed to retrieve secrets: {e}"
        print(error_message)
        notify_failure(error_message)
        return None, None

def new_relic_query(api_key, account_id, nrql):
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    query = f'{{actor {{account(id: {account_id}) {{nrql(query: "{nrql}", timeout: 60) {{results}}}}}}}}'
    response = requests.post("https://api.newrelic.com/graphql", headers=headers, json={"query": query})
    if response.status_code == 200:
        return response.json()
    else:
        error_message = f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}"
        print(error_message)
        notify_failure(error_message)
        return None

def save_to_bucket(bucket, prefix, data):
    if not bucket:
        error_message = "[ERROR] Bucket is not set."
        print(error_message)
        notify_failure(error_message)
        return None
    s3_client = boto3.client("s3")
    timestamp = datetime.now(ZoneInfo("Europe/London")).strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{prefix}newrelic_rmp_process_info_{timestamp}.json"
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
        error_message = f"[ERROR] Failed to upload JSON data to bucket {bucket}: {e}"
        print(error_message)
        notify_failure(error_message)
        return None

def lambda_handler(event, context):
    print("[INFO] Fetching API credentials from AWS Secrets Manager...")
    api_key, account_id = get_secret()
    if not api_key or not account_id:
        error_message = "Failed to retrieve API credentials."
        return {"statusCode": 500, "body": error_message}

    # Capture execution timestamp
    current_timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()

    # Step 1: Fetch unique hostname prefixes over 1 day
    prefix_query = "SELECT uniques(substring(hostname,0,7), 10000) as 'HostnamePrefix' FROM SystemSample SINCE 1 day ago"
    print("[INFO] Fetching unique hostname prefixes from New Relic...")
    prefix_data = new_relic_query(api_key, account_id, prefix_query)
    if not prefix_data:
        error_message = "Failed to retrieve hostname prefixes from New Relic."
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}
    prefix_results = prefix_data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    if not prefix_results or len(prefix_results) == 0:
        error_message = "No hostname prefixes available from New Relic."
        print(f"[WARNING] {error_message}")
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}
    stores = prefix_results[0].get("HostnamePrefix", [])
    if not stores:
        error_message = "No hostname prefixes available from New Relic."
        print(f"[WARNING] {error_message}")
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}
    print(f"[INFO] Retrieved {len(stores)} hostname prefixes.")

    # Step 2: Batch these prefixes and run detailed queries
    maxPrefixesPerBatch = 100
    queries = []
    index = 0
    while index < len(stores):
        batch = stores[index : index + maxPrefixesPerBatch]
        quoted = ",".join([f"'{prefix}'" for prefix in batch])
        detailed_query = (
            "SELECT latest(timestamp) FROM Metric WHERE metricName = 'windows_running_services' and state = 'running' "
            f"AND substring(hostname,0,7) in ({quoted}) "
            "FACET hostname, name SINCE 15 minutes ago LIMIT MAX"
        )
        queries.append(detailed_query)
        index += maxPrefixesPerBatch

    results = []
    print(f"[INFO] Running detailed queries in {len(queries)} batches...")
    for q in queries:
        data = new_relic_query(api_key, account_id, q)
        if data:
            batch_results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
            results.extend(batch_results)

    print(f"[INFO] Retrieved detailed process states for {len(results)} records.")

    # Step 3: Flatten/process output
    processed = []
    for item in results:
        facet = item.get('facet', [])
        if len(facet) != 2:
            continue
        hostname, name = facet
        processed.append({
            "hostname": hostname,
            "name": name,
            "new_relic_timestamp_latest": item.get('latest.timestamp'),
            "api_exe_timestamp": current_timestamp
        })

    # Step 4: Save output to both S3 buckets
    print("[INFO] Saving data to TARGET_BUCKET...")
    target_url = save_to_bucket(TARGET_BUCKET, S3_PREFIX, processed)
    print("[INFO] Saving data to DATASHARE_BUCKET...")
    datashare_url = save_to_bucket(DATASHARE_BUCKET, S3_PREFIX, processed)

    if target_url and datashare_url:
        return {
            "statusCode": 200,
            "body": f"Processed data saved to TARGET_BUCKET: {target_url} and DATASHARE_BUCKET: {datashare_url}"
        }
    else:
        error_message = "Failed to save data to one or both buckets."
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}
