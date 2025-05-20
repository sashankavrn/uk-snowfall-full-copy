import requests
import json
import boto3
import os
from datetime import datetime, timedelta

# AWS Config
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"
S3_BUCKET = os.environ.get("TARGET_BUCKET")
S3_PREFIX = "newrelic/newrelic_digital_3po_foe_response/"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# Send SNS Notification on failure
def send_sns_notification(message):
    if not SNS_TOPIC_ARN:
        print("[WARNING] SNS_TOPIC_ARN is not set.")
        return
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        full_message = f"[{timestamp}] {message}"
        boto3.client("sns").publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="NEWRELIC-DIGITAL-3PO-FOE-RESPONSE LAMBDA",
            Message=full_message
        )
        print(f"[INFO] SNS notification sent.")
    except Exception as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

# Retrieve secret
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

# Query New Relic
def new_relic_query(api_key, account_id, nrql):
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key
    }
    payload = json.dumps({
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
    response = requests.post("https://api.newrelic.com/graphql", headers=headers, data=payload)
    if response.status_code == 200:
        return response.json()
    print(f"[ERROR] Failed to fetch data: {response.status_code}, {response.text}")
    return None

# Save to S3
def save_to_s3(data):
    if not S3_BUCKET:
        print("[ERROR] S3 Bucket environment variable `TARGET_BUCKET` is not set.")
        return None
    s3_client = boto3.client("s3")
    timestamp = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
    s3_key = f"{S3_PREFIX}newrelic_digital_3po_foe_response_{timestamp}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(data, indent=4),
            ContentType="application/json"
        )
        print(f"[SUCCESS] Uploaded to s3://{S3_BUCKET}/{s3_key}")
        return f"s3://{S3_BUCKET}/{s3_key}"
    except Exception as e:
        print(f"[ERROR] Failed to upload JSON data to S3: {e}")
        return None

# Lambda Entry
def lambda_handler(event, context):
    print("[INFO] Fetching API credentials...")
    api_key, account_id = get_secret()
    if not api_key or not account_id:
        send_sns_notification("Failed to retrieve API credentials.")
        return {"statusCode": 500, "body": "Failed to retrieve API credentials."}

    # Calculate last full hour in UTC
    now = datetime.utcnow()
    this_hour_end = now.replace(minute=0, second=0, microsecond=0)
    last_hour_start = this_hour_end - timedelta(hours=1)

    since_str = last_hour_start.strftime("%Y-%m-%d %H:%M:%S")
    until_str = this_hour_end.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[INFO] Querying logs from {since_str} until {until_str}")

    # Build NRQL Query with dynamic SINCE and UNTIL
    query = f"""
        SELECT uniqueCount(aparse(message, '%VALUES%, *,%')) as Count
        FROM Log
        WHERE application = 'hds'
          and market in ('uk','ie')
          and (message like '%FOE returned foeErrorCode:%' or message like '%FOERespon%')
          and action in ('Release', 'SubmitOrder', 'SubmitOrderV2')
          and (not aparse(message, '%VALUES%,%,%,%,%,%,%,%,% *, Sql%') is null)
        FACET 
          aparse(message, '%VALUES%,%,%, *,%') as 'Restaurant', 
          aparse(message,'%VALUES%,%,%,%,%,%,%,% *,%') as 'FOE Response',
          aparse(message, '%VALUES%,%,%,%,%,%,%,%,% *,%') as '3PO Response',
          aparse(message, '%VALUES%,%,%,%,%,%,%,%,%,% *, Sql%') as '3PO Response Description'
        SINCE '{since_str}' UNTIL '{until_str}' 
        LIMIT MAX
    """

    print("[INFO] Sending query to New Relic...")
    data = new_relic_query(api_key, account_id, query)
    if not data:
        send_sns_notification("Failed to retrieve log data from New Relic.")
        return {"statusCode": 500, "body": "Failed to retrieve log data from New Relic."}

    results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    if not results:
        send_sns_notification("No log data returned from New Relic.")
        return {"statusCode": 204, "body": "No log data returned from New Relic."}

    print(f"[INFO] Retrieved {len(results)} entries. Uploading to S3...")
    s3_url = save_to_s3(results)
    if not s3_url:
        send_sns_notification("Data retrieval succeeded, but failed to save to S3.")
        return {"statusCode": 500, "body": "Failed to save data to S3."}

    return {
        "statusCode": 200,
        "body": f"Processed data saved to {s3_url}"
    }
