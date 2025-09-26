import boto3
import time
import json
import os
from datetime import datetime
from boto3.dynamodb.conditions import Attr

# Read config from environment variables
DYNAMO_REGION   = os.environ.get("DYNAMO_REGION", "eu-central-1")
RULES_TABLE     = os.environ["RULES_TABLE"]
TICKETS_TABLE   = os.environ["TICKETS_TABLE"]
ATHENA_REGION   = os.environ.get("ATHENA_REGION", "eu-central-1")
ATHENA_OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]

# DynamoDB clients
dynamodb = boto3.resource('dynamodb', region_name=DYNAMO_REGION)
rules_table = dynamodb.Table(RULES_TABLE)
tickets_table = dynamodb.Table(TICKETS_TABLE)

# Athena client
athena = boto3.client('athena', region_name=ATHENA_REGION)

def lambda_handler(event, context):
    print(f"Fetching rules from DynamoDB table: {RULES_TABLE} in {DYNAMO_REGION}...")
    rules = get_rules()

    for rule in rules:
        if not rule.get("active", False):
            continue

        print(f"Checking rule {rule['rule_id']}...")

        athena_result = query_athena(
            rule['query'],
            rule['database'],
        )

        if athena_result and evaluate_rule(rule, athena_result):
            print(f"Rule {rule['rule_id']} violated. Checking tickets...")
            if not ticket_exists(rule['rule_id']):
                print("No existing ticket found. Creating new ticket...")
                create_ticket(rule)
            else:
                print("Ticket already exists. Skipping...")
        else:
            print(f"Rule {rule['rule_id']} not violated.")

    return {"status": "completed"}


def get_rules():
    response = rules_table.scan()
    return response.get('Items', [])


def query_athena(athena_query, database):
    query = f'{athena_query}'
    print(f"Running Athena query: {query}")

    response = athena.start_query_execution(
        QueryString=query,
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
        print(rows)
        if len(rows) > 1:
            last_row = rows[1]['Data']
            record = {
                'restaurant_number': last_row[0]['VarCharValue'],
                'message': last_row[1]['VarCharValue']
            }
            return record
    return None


def evaluate_rule(rule, record):
    return record


def ticket_exists(rule_id):
    response = tickets_table.scan(
        FilterExpression=Attr('rule_id').eq(rule_id) & Attr('status').eq('OPEN')
    )
    return len(response.get('Items', [])) > 0


def create_ticket(rule):
    ticket_id = f"INC{int(time.time())}"
    item = {
        'ticket_id': ticket_id,
        'rule_id': rule['rule_id'],
        'status': 'OPEN',
        'created_at': datetime.utcnow().isoformat()
    }
    tickets_table.put_item(Item=item)
    print(f"Mock ticket created: {ticket_id}")
