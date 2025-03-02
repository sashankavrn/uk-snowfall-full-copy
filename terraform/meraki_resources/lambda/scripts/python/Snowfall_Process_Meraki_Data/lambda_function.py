import boto3
import json
import re


def lambda_handler(event, context):
    #'s3://snowfall-dev-meraki-landing/meraki/device_list_2025-01-17_02-01-18.json'
    # s3://snowfall-dev-meraki-processed


    # S3 client
    s3 = boto3.client('s3')

    print(event)
    print(event['detail']['bucket']['name'])
    print(event['detail']['object']['key'])

    source_bucket = event['detail']['bucket']['name']  # Source bucket
    source_key = event['detail']['object']['key']  # Path to the JSON file in the source bucket
    destination_bucket = 'snowfall-dev-meraki-processed'  # Destination bucket
    destination_key = source_key.replace(".json", "_formatted.json")  # Path to save the NDJSON file in the destination bucket

    # Fetch JSON file from the source bucket
    response = s3.get_object(Bucket=source_bucket, Key=source_key)
    content = response['Body'].read().decode('utf-8')

    # Load the JSON content
    data = json.loads(content)

    # Convert to NDJSON format with extracted location number
    ndjson_lines = []
    location_pattern = re.compile(r"-(\d+)\s#")  # Regex to extract location number

    if isinstance(data, list):  # Handle JSON array
        for obj in data:
            # Extract location number from device_name
            match = location_pattern.search(obj.get('device_name', ''))
            location_number = match.group(1) if match else -1
            # Add location number as a new field
            obj['restaurant_id'] = int(location_number)
            ndjson_lines.append(json.dumps(obj))
    elif isinstance(data, dict):  # Handle a single JSON object
        match = location_pattern.search(data.get('device_name', ''))
        location_number = match.group(1) if match else None
        data['location'] = location_number
        ndjson_lines.append(json.dumps(data))
    else:
        raise ValueError("Unexpected JSON structure. Expected an object or array.")

    # Create NDJSON content as a single string
    ndjson_content = '\n'.join(ndjson_lines)

    # Save NDJSON to the destination bucket
    s3.put_object(Bucket=destination_bucket, Key=destination_key, Body=ndjson_content)

    print(f"Formatted JSON with location added saved to s3://{destination_bucket}/{destination_key}")
