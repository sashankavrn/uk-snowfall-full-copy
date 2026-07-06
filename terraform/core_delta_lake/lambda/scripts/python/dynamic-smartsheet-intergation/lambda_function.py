import json
import os
import re
import base64
import urllib.request
import urllib.parse
import boto3
from datetime import datetime, timezone
from botocore.exceptions import BotoCoreError, ClientError

s3 = boto3.client("s3")

# --------------------- CONFIG ---------------------
BASE_URL = "https://api.smartsheet.com/2.0"
S3_BUCKET = os.environ.get('TARGET_BUCKET')
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

# LIST SMARTSHEET SHEET IDS TO FETCH
sheet_ids = [
    "4783904805676932",
    "4824729111187332"
]
# -------------------------------------------------


def notify_failure(message):
    """Lightweight failure notifier so get_secret() does not NameError."""
    print(f"[FAILURE NOTIFICATION] {message}")


# -------------------------------------------------
# Get API Key from Secrets Manager
# -------------------------------------------------
def get_secret():
    """Retrieve API key from AWS Secrets Manager."""
    secret_name = "uk-snowfall"
    region_name = "eu-central-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            return f"{secret['uk-snowfall-smartsheet-api-key']}"
        else:
            raise ValueError("SecretString not found in response")
    except (BotoCoreError, ClientError) as e:
        error_message = f"Failed to retrieve API key: {e}"
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return None


# -------------------------------------------------
# Get sheet from Smartsheet API
# -------------------------------------------------
def get_sheet(sheet_id, token):
    url = f"{BASE_URL}/sheets/{sheet_id}?exclude=nonexistentCells"
    print(f"[INFO] Calling API {url}.")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


# -------------------------------------------------
# Transform data to rows
# -------------------------------------------------
def transform_sheet(sheet):
    columns = sheet.get("columns", [])
    rows = sheet.get("rows", [])
    column_map = {c["id"]: c["title"] for c in columns}
    column_names = list(column_map.values())
    output = []
    for row in rows:
        row_obj = {col: None for col in column_names}
        for cell in row.get("cells", []):
            col_name = column_map.get(cell.get("columnId"))
            if col_name:
                row_obj[col_name] = cell.get("displayValue", cell.get("value"))
        output.append(row_obj)
    return output


# -------------------------------------------------
# Get clean S3-safe filename
# -------------------------------------------------
def sanitise_name(name):
    name = re.sub(r"[\\/]+", "-", name)
    name = re.sub(r"[^A-Za-z0-9._ -]", "-", name)
    name = re.sub(r"\s+", "-", name)
    return name.strip("-._ ")


# -------------------------------------------------
# Export sheet
# -------------------------------------------------
def export_sheet(sheet_id, token):
    print(f"[INFO] Getting Smartsheet ID {sheet_id}...")
    sheet = get_sheet(sheet_id, token)
    sheet_name = sheet.get("name", f"sheet-{sheet_id}")
    safe_name = sanitise_name(sheet_name)
    key = f"smartsheet/{safe_name}.json"
    rows = transform_sheet(sheet)
    payload = {
        "sheet_id": sheet_id,
        "sheet_name": sheet_name,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "data": rows
    }
    print(f"[INFO] Exporting to S3 | Bucket: {S3_BUCKET} | Key: {key}.")
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(payload, default=str),
        ContentType="application/json"
    )


# -------------------------------------------------
# Lambda entry point
# -------------------------------------------------
def lambda_handler(event, context):
    token = get_secret()
    for sheet_id in sheet_ids:
        export_sheet(sheet_id, token)
    return {
        "statusCode": 200
    }
