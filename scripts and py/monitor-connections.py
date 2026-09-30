import boto3
import os
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "dev_websocket_connections"))

def get_threshold_time():
    # Read timeout from env (examples: "30", "45m", "1h")
    timeout_value = os.environ.get("STALE_TIMEOUT", "1h").lower()

    if timeout_value.endswith("h"):
        hours = int(timeout_value.replace("h", ""))
        delta = timedelta(hours=hours)
    elif timeout_value.endswith("m"):
        minutes = int(timeout_value.replace("m", ""))
        delta = timedelta(minutes=minutes)
    else:
        # If only number provided → treat as minutes
        delta = timedelta(minutes=int(timeout_value))

    return datetime.utcnow() - delta


def handler(event, context):
    print("Monitoring WebSocket connections...")

    threshold_time = get_threshold_time()
    threshold_iso = threshold_time.isoformat()

    print("Threshold time:", threshold_iso)

    response = table.scan(
        FilterExpression=(
            Attr("status").eq("disconnected") |
            Attr("last_seen").lt(threshold_iso)
        )
    )

    items = response.get("Items", [])

    if items:
        print("Found stale or disconnected connections:")
        for item in items:
            print(item)
    else:
        print("No stale or disconnected connections found.")

    return {
        "statusCode": 200,
        "body": f"Checked {len(items)} stale/disconnected connections"
    }
