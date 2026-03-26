import json
import boto3
import os
import uuid
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def lambda_handler(event, context):
    try:
        print("=== FULL EVENT ===")
        print(json.dumps(event, indent=2))

        body = event.get("body")

        print("=== RAW BODY ===")
        print(body)

        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body

        print("=== PARSED PAYLOAD ===")
        print(json.dumps(payload, indent=2))

        if not payload:
            return response(400, "Invalid payload")

        alert_id = str(uuid.uuid4())

        event_type = payload.get("type")
        alert_object = payload.get("alert", {})

        created_at = datetime.utcnow().isoformat()

        item = {
            "alert_id": alert_id,
            "type": event_type,
            "alert": alert_object,
            "created_at": created_at
        }

        # 🔹 Log item before insert
        print("=== DYNAMODB ITEM ===")
        print(json.dumps(item, indent=2))

        # 🔹 Insert into DynamoDB
        table.put_item(Item=item)

        print(f"Successfully stored alert_id: {alert_id}")

        return response(200, {
            "message": "Stored successfully",
            "alert_id": alert_id
        })

    except Exception as e:
        print("ERROR OCCURRED")
        print(str(e))

        return response(500, str(e))


def response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body)
    }