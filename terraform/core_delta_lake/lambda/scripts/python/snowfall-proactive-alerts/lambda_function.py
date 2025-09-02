import boto3
import time
import json
from datetime import datetime

# DynamoDB clients (region eu-west-2)
dynamodb = boto3.resource('dynamodb', region_name='eu-west-2')
rules_table = dynamodb.Table('dev_incident_rules')
tickets_table = dynamodb.Table('dev_service_now_tickets')

# Athena client (region eu-central-1)
athena = boto3.client('athena', region_name='eu-central-1')

def lambda_handler(event, context):
    print("Fetching rules from DynamoDB...")
    rules = get_rules()

    for rule in rules:
        if not rule.get("active", False):
            continue

        print(f"Checking rule {rule['rule_id']}...")

        athena_result = query_athena(
            rule['athena_database'],
            rule['athena_table'],
            rule['metric']
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


def query_athena(database, table, metric):
    query = f'SELECT server_id, timestamp, {metric} FROM "{database}"."{table}" ORDER BY timestamp DESC LIMIT 1;'
    print(f"Running Athena query: {query}")

    output_location = "s3://eu-central1-dev-uk-snowfall-temp-295446674139/alerts/"
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_location}
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
        if len(rows) > 1:
            # First row = header
            last_row = rows[1]['Data']
            record = {
                'server_id': last_row[0]['VarCharValue'],
                'timestamp': last_row[1]['VarCharValue'],
                metric: float(last_row[2]['VarCharValue'])
            }
            return record
    return None


def evaluate_rule(rule, record):
    metric = rule['metric']
    threshold = float(rule['threshold'])
    comparison = rule['comparison']

    value = record.get(metric, 0)
    print(f"Evaluating {metric}: {value} {comparison} {threshold}")

    if comparison == "gt":
        return value > threshold
    elif comparison == "lt":
        return value < threshold
    return False


def ticket_exists(rule_id):
    response = tickets_table.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('rule_id').eq(rule_id) & 
                        boto3.dynamodb.conditions.Attr('status').eq('OPEN')
    )
    return len(response.get('Items', [])) > 0


def create_ticket(rule):
    # For now, just store in DynamoDB (instead of real ServiceNow)
    ticket_id = f"INC{int(time.time())}"
    item = {
        'ticket_id': ticket_id,
        'rule_id': rule['rule_id'],
        'status': 'OPEN',
        'created_at': datetime.utcnow().isoformat()
    }
    tickets_table.put_item(Item=item)
    print(f"Mock ticket created: {ticket_id}")
