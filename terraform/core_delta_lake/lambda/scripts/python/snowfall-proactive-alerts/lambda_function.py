
import uuid
import base64
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
import boto3
import time
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from boto3.dynamodb.conditions import Attr

# WebSocket config
WEBSOCKET_ENDPOINT = os.environ["WEBSOCKET_ENDPOINT"]
CONNECTIONS_TABLE  = os.environ["TABLE_NAME"]




# Read config from environment variables
DYNAMO_REGION    = os.environ.get("DYNAMO_REGION", "eu-central-1")
RULES_TABLE      = os.environ["RULES_TABLE"]
TICKETS_TABLE    = os.environ["TICKETS_TABLE"]
ATHENA_REGION    = os.environ.get("ATHENA_REGION", "eu-central-1")
ATHENA_OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]

# DynamoDB clients
dynamodb = boto3.resource('dynamodb', region_name=DYNAMO_REGION)
rules_table = dynamodb.Table(RULES_TABLE)
tickets_table = dynamodb.Table(TICKETS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)

# Athena client
athena = boto3.client('athena', region_name=ATHENA_REGION)
sns_client = boto3.client('sns')

def lambda_handler(event, context):
    execution_time = datetime.now(ZoneInfo("Europe/London")).isoformat()
    print(f"[INFO] Lambda execution started at {execution_time}")
    print(f"[INFO] Fetching rules from DynamoDB table: {RULES_TABLE} in {DYNAMO_REGION}...")

    rules = get_rules()

    for rule in rules:
        if not rule.get("active", False):
            continue

        print(f"[INFO] Checking rule {rule['rule_id']} at {datetime.now(ZoneInfo('Europe/London')).isoformat()}")

        athena_result = query_athena(
            rule['query'],
            'uk_snowfall_processed',
        )

        if athena_result and evaluate_rule(rule, athena_result):
            print(f"[INFO] Rule {rule['rule_id']} violated. Checking tickets...")
            if not ticket_exists(rule['rule_id']):
                print("[INFO] No existing ticket found. Creating new ticket...")
                create_ticket(rule, athena_result)
            else:
                print("[INFO] Ticket already exists. Skipping...")
        else:
            print(f"[INFO] Rule {rule['rule_id']} not violated.")

    return {"status": "completed"}

def get_rules():
    response = rules_table.scan()
    return response.get('Items', [])

def query_athena(athena_query, database):
    print(f"[INFO] Running Athena query: {athena_query}")
    response = athena.start_query_execution(
        QueryString=athena_query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_S3}
    )

    query_execution_id = response['QueryExecutionId']
    state = 'RUNNING'

    while state in ['RUNNING', 'QUEUED']:
        time.sleep(2)
        result = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = result['QueryExecution']['Status']['State']

    if state == 'SUCCEEDED':
        results = athena.get_query_results(QueryExecutionId=query_execution_id)
        rows = results['ResultSet']['Rows']
        print(f"[INFO] Athena returned {len(rows)} rows")

        if len(rows) > 1:
            last_row = rows[1]['Data']
            print(rows)
            record = {
                'restaurant_number': last_row[0]['VarCharValue'],
                'message': last_row[1]['VarCharValue']
            }

            return record
    return None

def evaluate_rule(rule, record):
    return record  # Placeholder for actual logic

def ticket_exists(rule_id):
    response = tickets_table.scan(
        FilterExpression=Attr('rule_id').eq(rule_id) & Attr('status').eq('OPEN')
    )
    print(response)
    print("length"), len(response.get('Items'))
    return len(response.get('Items', [])) > 0

def create_ticket(rule, athena_result):
    print(athena_result)
    ticket_id = f"INC{int(time.time())}"
    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
    item = {
        'restaurent number': athena_result['restaurant_number'],
        'message': athena_result['message'],
        'ticket_id': ticket_id,
        'rule_id': rule['rule_id'],
        'status': 'OPEN',
        'created_at': timestamp
    }
    tickets_table.put_item(Item=item)
    print(f"[INFO] Ticket created: {ticket_id} at {timestamp}")
    send_snsnotification(rule, item, athena_result)
    send_system_info_script(
        restaurant_number=athena_result["restaurant_number"]
    )


def send_snsnotification(rule, item, rows):
    # Format message for email
    subject = f"Proactive alerts : {rule['incident_description']}"
    message = json.dumps(item, indent=2)
    print(message)
    
    # Publish to SNS
    response = sns_client.publish(
        TopicArn=os.environ["SNS_TOPIC_ARN"],
        Subject=subject,
        Message=message
    )
    print(response)

def send_system_info_script(restaurant_number):
    print(f"[INFO] Triggering system_info.py via WebSocket for restaurant {restaurant_number}")

    connections_table = dynamodb.Table(os.environ["TABLE_NAME"])

    endpoint_url = os.environ["WEBSOCKET_ENDPOINT"].replace("wss://", "https://").rstrip("/")
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)

    # Load script (same as existing lambda)
    script_path = "/var/task/system_info.py"
    with open(script_path, "r") as f:
        script_content = f.read()

    encoded_script = base64.b64encode(script_content.encode()).decode()

    response = connections_table.scan(
        FilterExpression=Attr("restaurant_number").eq(str(restaurant_number))
                        & Attr("status").eq("connected")
    )

    for item in response.get("Items", []):
        connection_id = item.get("connectionId") or item.get("connection_id")
        device_id = item.get("device_id")
        script_name = "health_check.py"
        folder_path = "C:\\GITHUB2025\\agent-scripts\\"
        script_path = folder_path + script_name
        message = {
            "command_id": str(uuid.uuid4()),
            "script_name": script_name,
            "action": "trigger_script",
            "script_path": script_path,
            "save_results": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode("utf-8")
            )
            print(f"[INFO] Script sent to device {device_id}")

        except apigw.exceptions.GoneException:
            print(f"[WARN] Connection {connection_id} is gone, cleaning up")
            connections_table.delete_item(
                Key={
                    "restaurant_number": item["restaurant_number"],
                    "device_id": device_id
                }
            )

        except ClientError as e:
            print("[ERROR] Failed to send WebSocket message:", e)