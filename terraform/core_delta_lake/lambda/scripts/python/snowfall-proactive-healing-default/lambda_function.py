import boto3
import os
import json
import base64
import traceback
import uuid
from datetime import datetime

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
apigw = boto3.client('apigatewaymanagementapi', endpoint_url=os.environ['WEBSOCKET_ENDPOINT'])

def lambda_handler(event, context):
    print("=== Lambda Triggered: Send Script to WebSocket Client ===")
    print("Incoming event:", json.dumps(event, indent=2))

    # Extract parameters from event or environment
    device_id =  'device-001' # event.get("device_id")
    restaurant_number = '12' # event.get("restaurant_number") 
    script_name = event.get("script_name", "system_info.py")
    save_results = event.get("save_results", True)

    if not device_id or not restaurant_number:
        print("Missing 'device_id' or 'restaurant_number'")
        return {"statusCode": 400, "body": "Missing required parameters"}

    print(f"Target device_id: {device_id}")
    print(f"Restaurant number: {restaurant_number}")
    print(f"Requested script: {script_name}")
    print(f"Save results flag: {save_results}")

    # Step 1 — Read Python script content
    script_path = f"/var/task/{script_name}"
    try:
        with open(script_path, "r") as f:
            script_content = f.read()
        print(f"Successfully read script file: {script_path} (length={len(script_content)} bytes)")
    except FileNotFoundError:
        print(f"Script not found at path: {script_path}")
        return {"statusCode": 404, "body": f"Script {script_name} not found"}
    except Exception as e:
        print("Error reading script file:", str(e))
        print(traceback.format_exc())
        return {"statusCode": 500, "body": "Error reading script"}

    encoded_script = base64.b64encode(script_content.encode()).decode()
    print("Script successfully base64-encoded")

    # Step 2 — Fetch connection ID from DynamoDB
    try:
        print(f"Looking up device_id={device_id}, restaurant_number={restaurant_number} in DynamoDB table={os.environ['TABLE_NAME']}")
        resp = table.get_item(
            Key={
                "restaurant_number": restaurant_number,
                "device_id": device_id
            }
        )
    except Exception as e:
        print(f"DynamoDB get_item failed: {e}")
        print(traceback.format_exc())
        return {"statusCode": 500, "body": "DynamoDB query failed"}

    if "Item" not in resp:
        print(f"Device {device_id} not found in DynamoDB (possibly disconnected)")
        return {"statusCode": 404, "body": f"Device {device_id} not found or disconnected"}

    item = resp["Item"]
    connection_id = item.get("connection_id") or item.get("connectionId")
    print(f"Found active connectionId: {connection_id}")

    # Step 3 — Construct WebSocket payload
    command_id = str(uuid.uuid4())
    message = {
        "action": "run_script",
        "command_id": command_id,
        "script_name": script_name,
        "script_content": encoded_script,
        "save_results": save_results,
        "timestamp": datetime.utcnow().isoformat(),
    }
    print("Prepared WebSocket payload:", json.dumps(message)[:400], "...")

    # Step 4 — Send message via API Gateway
    try:
        print("🚀 Sending script to WebSocket client...")
        apigw.post_to_connection(ConnectionId=connection_id, Data=json.dumps(message))
        print(f"Successfully sent script '{script_name}' to device '{device_id}'")
        result = "success"
    except Exception as e:
        print("Error sending message via WebSocket:", str(e))
        print(traceback.format_exc())
        result = "error"

    # Step 5 — Return structured Lambda response
    response_payload = {
        "device_id": device_id,
        "restaurant_number": restaurant_number,
        "script_name": script_name,
        "command_id": command_id,
        "save_results": save_results,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
    }

    print("=== Lambda Execution Complete ===")
    print("Response:", json.dumps(response_payload, indent=2))
    return {
        "statusCode": 200 if result == "success" else 500,
        "body": json.dumps(response_payload),
    }