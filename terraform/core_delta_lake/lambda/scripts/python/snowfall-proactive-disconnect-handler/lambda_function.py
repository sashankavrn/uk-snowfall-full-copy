import boto3
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'dev_websocket_connections'))

def handler(event, context):
    print("Disconnect event:", event)

    connection_id = event['requestContext']['connectionId']

    # Find the record with this connectionId
    response = table.scan(
        FilterExpression=Key('connectionId').eq(connection_id)
    )

    if 'Items' in response and len(response['Items']) > 0:
        item = response['Items'][0]
        restaurant_number = item['restaurant_number']
        device_id = item['device_id']

        # Mark as disconnected
        table.update_item(
            Key={
                'restaurant_number': restaurant_number,
                'device_id': device_id
            },
            UpdateExpression="SET #s = :status, last_seen = :time",
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':status': 'disconnected',
                ':time': datetime.utcnow().isoformat()
            }
        )

        print(f"Marked {device_id} ({restaurant_number}) as disconnected")

    else:
        print(f"No record found for connectionId: {connection_id}")

    return {'statusCode': 200, 'body': 'Disconnected marked'}