import boto3
import os
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME"))

def handler(event, context):
    print(event)
    connection_id = event["requestContext"]["connectionId"]
    params = event.get("queryStringParameters") or {}

    # restaurant_number = params.get("restaurantnumber", "unknown")
    # device_id = params.get("deviceid", connection_id)
    # machine_name = params.get("machine", "unknown")

    # auth_ctx = event["requestContext"]["authorizer"]
    auth_ctx = event["requestContext"].get("authorizer")
    if not auth_ctx:
        return {"statusCode": 401, "body": "Unauthorized"}

    restaurant_number = auth_ctx["restaurant_number"]
    device_id = auth_ctx["device_id"]
    machine_name = auth_ctx["machine"]

    table.put_item(
        Item={
            "restaurant_number": restaurant_number,
            "device_id": device_id,
            "connectionId": connection_id,
            "machineName": machine_name,
            "status": "connected",
            "last_seen": datetime.utcnow().isoformat(),
        }
    )

    return {"statusCode": 200, "body": f"Connected: {connection_id}"}