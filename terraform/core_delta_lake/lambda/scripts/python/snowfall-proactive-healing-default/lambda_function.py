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
results_table = dynamodb.Table(os.environ.get("RESULTS_TABLE_NAME", "WebSocketResults"))



def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        body = {}

    print("Incoming event:", json.dumps(event))

    connection_id = event["requestContext"]["connectionId"]
    endpoint_url = os.environ["WEBSOCKET_ENDPOINT"]
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)

    action = body.get("action", "heartbeat")

    if action == "register":
        restaurant_number = body["restaurant_number"]
        device_id = body["device_id"]
        machine_name = body.get("machine", "unknown")

        table.put_item(
            Item={
                "restaurant_number": restaurant_number,
                "device_id": device_id,
                "connectionId": connection_id,
                "machineName": machine_name,
                "last_seen": datetime.utcnow().isoformat(),
                "status": "connected",
            }
        )

        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"message": f"✅ Registered {device_id} successfully!"}),
        )

    elif action == "heartbeat":
        restaurant_number = body["restaurant_number"]
        device_id = body["device_id"]

        table.update_item(
            Key={"restaurant_number": restaurant_number, "device_id": device_id},
            UpdateExpression="SET last_seen = :t, #s = :s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":t": datetime.utcnow().isoformat(),
                ":s": "connected",
            },
        )

        print(f"💓 Heartbeat received from {device_id}")
        apigw.post_to_connection(
            ConnectionId=connection_id, Data=json.dumps({"message": "pong"})
        )


    elif action == "save_results":
        restaurant_number = body.get("restaurant_number")
        device_id = body.get("device_id")
        command_id = body.get("command_id", "unknown")
        script_name = body.get("script_name", "unknown")
        result_output = body.get("result_output", "")
        stderr = body.get("stderr", "")
        execution_status = body.get("execution_status", "success")
        timestamp = datetime.utcnow().isoformat()

        print(f"💾 Saving results for {device_id}, command_id={command_id}")

        results_table.put_item(
            Item={
                "restaurant_number": restaurant_number,
                "result_id": command_id,
                "device_id": device_id,
                "stderr": stderr,
                "script_name": script_name,
                "result_output": result_output,
                "execution_status": execution_status,
                "saved_at": timestamp,
            }
        )

        print(f"✅ Results saved successfully for {device_id}")
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"message": f"✅ Results saved for {device_id} ({script_name})"}),
        )

    else:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"message": "Unknown action"}),
        )

    return {"statusCode": 200, "body": "Processed successfully"}
