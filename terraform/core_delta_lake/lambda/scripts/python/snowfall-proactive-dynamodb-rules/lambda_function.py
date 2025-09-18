import boto3
import os

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb', region_name=os.environ['DYNAMO_REGION'])

    table_name = os.environ['RULES_TABLE']

    rule_item = {
        'rule_id':              {'S': '1'},
        'active':               {'BOOL': True},
        'athena_database':      {'S': 'uk_snowfall_processed'},
        'athena_table':         {'S': 'newrelic_rmp_device_metrics'},
        'comparison':           {'S': 'gt'},
        'threshold':              {'S': '95'},
        'incident_description': {'S': 'Disk usage above 90%'},
        'metric':               {'S': 'average_disk_used_percent'},
    }

    dynamodb.put_item(TableName=table_name, Item=rule_item)

    return {
        'statusCode': 200,
        'body': 'Rule inserted successfully'
    }
