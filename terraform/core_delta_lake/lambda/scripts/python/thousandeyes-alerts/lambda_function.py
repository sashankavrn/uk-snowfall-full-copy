import json
import os
import boto3
from datetime import datetime

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ.get("TICKET_TABLE_NAME")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    print("Incoming event:", json.dumps(event))

    # ----------------------------------------------------
    # 1. Parse ThousandEyes webhook payload
    # ----------------------------------------------------
    try:
        body = json.loads(event.get("body", "{}"))
        print("Parsed ThousandEyes payload:", body)
    except Exception as e:
        print("Error parsing JSON:", str(e))
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Invalid JSON"})
        }

    # ----------------------------------------------------
    # 2. Extract useful fields from ThousandEyes payload
    # ----------------------------------------------------
    alert_id = body.get("alertId", "unknown")
    severity = body.get("severity", "unknown")
    test_name = body.get("testName", "unknown")
    timestamp = body.get("timestamp", datetime.utcnow().isoformat())

    # ----------------------------------------------------
    # 3. Create ticket entry in DynamoDB
    # ----------------------------------------------------
    try:
        ticket_id = f"{alert_id}-{int(datetime.utcnow().timestamp())}"

        item = {
            "ticket_id": ticket_id,
            "alert_id": str(alert_id),
            "severity": severity,
            "test_name": test_name,
            "received_at": datetime.utcnow().isoformat(),
            "payload": body
        }

        table.put_item(Item=item)
        print("Ticket stored:", item)

    except Exception as e:
        print("DynamoDB error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Failed to create ticket"})
        }

    # ----------------------------------------------------
    # 4. Return success
    # ----------------------------------------------------
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Ticket created",
            "ticket_id": ticket_id,
            "alert_id": alert_id,
            "severity": severity,
            "test_name": test_name
        })
    }
