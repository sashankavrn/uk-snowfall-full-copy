import boto3
import os

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb', region_name=os.environ['DYNAMO_REGION'])

    table_name = os.environ['RULES_TABLE']

    rule_item = {
        'rule_id':              {'S': '1'},
        'active':               {'BOOL': True},
        'athena_database':      {'S': 'infra_metrics'},
        'athena_table':         {'S': 'cpu_metrics'},
        'comparison':           {'S': 'gt'},
        'incident_description': {'S': 'CPU usage above 80%'},
        'metric':               {'S': 'cpu_usage'},
    }

    dynamodb.put_item(TableName=table_name, Item=rule_item)

    return {
        'statusCode': 200,
        'body': 'Rule inserted successfully'
    }
