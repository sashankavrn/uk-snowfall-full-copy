import requests
import json
import boto3
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# AWS Secrets Manager Details
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# Amazon S3 Details
S3_BUCKET = os.environ.get("TARGET_BUCKET")
S3_PREFIX = "newrelic/newrelic_digital_gma_foe_response/"

# Send failure notification to SNS
def notify_failure(subject, message):
    sns_arn = os.environ.get("SNS_TOPIC_ARN")
    if not sns_arn:
        print("[WARNING] SNS_TOPIC_ARN not set. Skipping SNS notification.")
        return

    sns_client = boto3.client("sns")
    try:
        sns_client.publish(
            TopicArn=sns_arn,
            Subject=subject,
            Message=message
        )
        print("[INFO] Sent failure notification to SNS.")
    except ClientError as e:
        print(f"[ERROR] Failed to publish to SNS: {e}")

# Fetch Secrets from AWS Secrets Manager
def get_secret():
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

        return api_key, int(account_id)

    except Exception as e:
        print(f"[ERROR] Failed to retrieve secrets: {e}")
        return None, None

# Send NRQL query to New Relic
def new_relic_query(api_key, account_id, nrql):
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }

    query_payload = json.dumps({
        "query": f"""
        {{
          actor {{
            account(id: {account_id}) {{
              nrql(query: \"\"\"{nrql}\"\"\", timeout: 60) {{
                results
              }}
            }}
          }}
        }}
        """
    })

    print("[DEBUG] Sending query to New Relic:", query_payload)

    response = requests.post("https://api.newrelic.com/graphql", headers=headers, data=query_payload)

    if response.status_code == 200:
        response_json = response.json()
        print("[DEBUG] New Relic Response:", json.dumps(response_json, indent=2))
        return response_json
    else:
        print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
        return None

# Save JSON data to S3 with timestamped filename
def save_to_s3(data):
    if not S3_BUCKET:
        print("[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set.")
        return None

    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_digital_gma_foe_response_{timestamp}.json"

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

# Main Lambda handler
def lambda_handler(event, context):
    try:
        print("[INFO] Fetching API credentials from AWS Secrets Manager...")
        api_key, account_id = get_secret()

        if not api_key or not account_id:
            msg = "[ERROR] Missing API credentials. Aborting process."
            notify_failure("New Relic Lambda Failure", msg)
            return {"statusCode": 500, "body": msg}

        print(f"[INFO] Using New Relic Account ID: {account_id}")

        # Calculate last full hour in UTC
        now = datetime.utcnow()
        this_hour_end = now.replace(minute=0, second=0, microsecond=0)
        last_hour_start = this_hour_end - timedelta(hours=1)

        since_str = last_hour_start.strftime("%Y-%m-%d %H:%M:%S")
        until_str = this_hour_end.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[INFO] Querying New Relic from {since_str} until {until_str}")

        # Dynamic NRQL query
        query = f"""
            SELECT uniqueCount(substring(aparse(message, '%ORDER * :%'), 1, 36)) as 'Count' 
            FROM Log 
            WHERE market = 'uk' 
            AND message LIKE '%UpdateOrderStateAsync : MARKET UK : ORDER%' 
            AND (message LIKE '%UpdateOrderStatusAsync%' OR message LIKE '%DoFoeStoreStaging%') 
            FACET aparse(message, '%DoFoeStoreStaging : * :%'),  
            IF(length(aparse(message, '%FAULT : * :%')) > 0, aparse(message, '%FAULT : *'), 'No Fault') 
            SINCE '{since_str}' UNTIL '{until_str}' 
            LIMIT MAX
        """

        print("[INFO] Fetching New Relic digital response data...")
        data = new_relic_query(api_key, account_id, query)

        if not data:
            msg = "[ERROR] Failed to retrieve digital response log data from New Relic."
            notify_failure("New Relic Lambda Failure", msg)
            return {"statusCode": 500, "body": msg}

        results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])

        if not results:
            msg = "[WARNING] No digital response log data returned from New Relic."
            notify_failure("New Relic Lambda Warning", msg)
            return {"statusCode": 500, "body": msg}

        print(f"[INFO] Retrieved {len(results)} digital response log entries from New Relic.")
        print("[INFO] Saving to S3...")
        s3_url = save_to_s3(results)

        return {
            "statusCode": 200,
            "body": f"Processed data saved to {s3_url}" if s3_url else "Failed to save data to S3."
        }

    except Exception as e:
        error_message = f"[EXCEPTION] Lambda failed unexpectedly: {e}"
        print(error_message)
        notify_failure("New Relic Lambda Fatal Error", error_message)
        return {"statusCode": 500, "body": error_message}
