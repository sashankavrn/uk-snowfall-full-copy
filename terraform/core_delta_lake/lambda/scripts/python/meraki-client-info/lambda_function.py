import requests
import re
import json
import boto3
import time
import os
import math
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from botocore.exceptions import BotoCoreError, ClientError
s3 = boto3.client('s3')
ORG_ID = "662029145223463867"
SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"
MERAKI_BASE_URL = "https://api.meraki.com/api/v1"
PER_PAGE = 1000
BUCKET_NAME = os.environ.get('TARGET_BUCKET')

# CONFIGURATION ==============================================================================================
maxRuns = 50            # SET MAXIMUM NUMBER OF TIMES THIS FUNCTION CAN INVOKE ITSELF
networkPerRun = 500     # SET NUMBER OF NETWORKS TO LOOP THROUGH ON EVERY INVOKATION TO RETRIVE CLIENTS
minimumRemainingTime = 180000   # SET MINIMUM REMAINING TIME (IN MS) TO RESTART LAMBDA
#=============================================================================================================
# S3 LOCATIONS ===============================================================================================
TEMP_FILE_LOCATION_BUCKET_NAME = os.environ.get('TEMP_BUCKET')    # S3 BUCKET FOR TEMPORARY DATA
TEMP_FILE_LOCATION_OBJECT_KEY = 'meraki/client_info/'          # KEY FOR TEMPORARY DATA
OUTPUT_BUCKET = os.environ.get('TARGET_BUCKET')   # << NEED TO ADJUST LOCATION TO CORRECT S3 BUCKET FOR COMPLETED FILE!!! <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
OUTPUT_KEY = 'meraki/client_info/'             # << NEED TO ADJUST KEY FOR COMPLETED FILE!!!                           <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#=============================================================================================================
#=============================================================================================================

def get_secret():
    """Retrieve API key from AWS Secrets Manager."""
    secret_name = "uk-snowfall"
    region_name = "eu-central-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            return f"Bearer {secret['uk-snowfall-meraki-api-key']}"
        else:
            raise ValueError("SecretString not found in response")
    except (BotoCoreError, ClientError) as e:
        error_message = f"Failed to retrieve API key: {e}"
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return None

def notify_failure(message):
    return                                                   
    """Send SNS notification for a failure event."""
    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        print("[ERROR] SNS_TOPIC_ARN not set in environment variables.")
        return

    try:
        sns_client = boto3.client('sns')
        sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject="Meraki Client Lambda Failure Notification"
        )
        print("[INFO] SNS notification sent.")
    except ClientError as e:
        print(f"[ERROR] Failed to send SNS notification: {e}")

def extract_restaurant_number(name):
    """Extract restaurant number from device name."""
    match = re.search(r'-(\d+)', name)
    if match:
        return int(match.group(1)) 
    match = re.search(r'(\d+)', name)
    if match:
        return int(match.group(1)) 
    print(f"[WARNING] Could not get restaraunt number for: {name}")
    return -1

def merakiAPInetworkList(authToken, nextToken=None, retries=3):
    """Fetch Meraki networks using API with pagination."""
    url = "https://api.meraki.com/api/v1/organizations/662029145223463867/networks"
    params = {'perPage': '1000'}
    if nextToken:
        params['startingAfter'] = nextToken

    headers = {'Authorization': authToken}

    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            print(f"[INFO] Attempt {attempt}: Fetching Meraki networks...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            nextToken = None
            links = response.headers.get('Link', '').split(', ')
            for link in links:
                if 'rel=next' in link:
                    match = re.search(r'startingAfter=(\w+)', link)
                    if match:
                        nextToken = match.group(1)
                        break

            return response.json(), nextToken

        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 1))
                if retry_after < 10:
                        retry_after = 10 * attempt
                print(f"[WARNING] Rate limited (Attempt {attempt}). Retry in {retry_after} seconds...")
                time.sleep(retry_after)
            
            else:
                print(f"[WARNING] API request failed (Attempt {attempt}): {e}")
                if attempt <= retries:
                    time.sleep(4 ** attempt)

    print(f"[ERROR] API Request failed to retrieve networks. No more retries available.")
    return None, None
    
def merakiAPIclientList(authToken, nextToken=None, networkID=None, retries=5):
    """Fetch Meraki networks using API with pagination."""
    url = f"https://api.meraki.com/api/v1/organizations/662029145223463867/networks/{networkID}/clients"
    params = {'perPage': '1000', 'timespan': '86400'}
    if nextToken:
        params['startingAfter'] = nextToken

    headers = {'Authorization': authToken}

    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            print(f"[INFO] Attempt {attempt}: Fetching Meraki clients for network: {networkID}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            nextToken = None
            links = response.headers.get('Link', '').split(', ')
            for link in links:
                if 'rel=next' in link:
                    match = re.search(r'startingAfter=(\w+)', link)
                    if match:
                        nextToken = match.group(1)
                        break

            return response.json(), nextToken

        except requests.exceptions.RequestException as e:
            if e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 1))
                if retry_after < 20:
                        retry_after = 20 * attempt
                print(f"[WARNING] Rate limited (Attempt {attempt}). Retry in {retry_after} seconds...")
                time.sleep(retry_after)
            
            else:
                print(f"[WARNING] API request failed (Attempt {attempt}): {e}")
                if attempt <= retries:
                    time.sleep(4 ** attempt)

    print(f"[ERROR] API request failed. No more retries available.")
    return None, None

def invokeFunctionAgain(runCount, startIndex, networkList, clientList, runInstanceName, functionName):
    print("[INFO] Exporting temporary data file.")
    # Save client list to S3 location temporerily 

    payloadForS3 = {
        'runInstanceName': runInstanceName,
        'runCounter': runCount,
        'startIndex': startIndex,
        'networkList': networkList
    }
    json_data = json.dumps(payloadForS3) #, indent=4)
    s3_key = f"{TEMP_FILE_LOCATION_OBJECT_KEY}meraki-client-temp-data.json"

    exportFileToS3(bucket=TEMP_FILE_LOCATION_BUCKET_NAME, key=s3_key, body=json_data)

    # Invoke lambda again to get remaining clients.
    print("[INFO] Calling Lambda to get client information.")
    payload = {
        "runInstanceName": runInstanceName,
        "runCounter": runCount
        }
    client = boto3.client('lambda')
    response = client.invoke(
        FunctionName=functionName, 
        InvocationType='Event',
        Payload=json.dumps(payload).encode('utf-8')
    )
    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 202:
        print("[INFO] Called Lambda successfully.")
    else:
        error_message = f"Failed to call Lamdba: {response}."
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
    return

def exportFileToS3(bucket, key, body, maxAttempts=3):
    attempt = 0
    while attempt<=maxAttempts:
        attempt+=1
        print(f"[INFO] Attempt {attempt}: Exporting payload to: {bucket}/{key}")

        try:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType='application/json'
            )
            print(f"[SUCCESS] Payload exported to: {bucket}/{key}")
            return 

        except ClientError as e:
            print(f"[WARNING] Failed to export payload to S3: {e}")

    error_message = f"Failed to export payload to: {bucket}/{key}"
    print(f"[ERROR] {error_message}")
    notify_failure(error_message)

def exportPayload(clientList, runInstanceName, partNo, maxAttempts=3):
    json_data = json.dumps(clientList) #, indent=4)
    filename = f"client-list-{runInstanceName}-part-{partNo}.json"
    s3_key = f"{TEMP_FILE_LOCATION_OBJECT_KEY}{filename}"

    exportFileToS3(bucket=TEMP_FILE_LOCATION_BUCKET_NAME, key=s3_key, body=json_data)
    return

def lambda_handler(event, context):
    """AWS Lambda handler function."""

    authToken = get_secret()

    # Check authToken has been retrieved
    if not authToken:
        error_message = "API Key retrieval failed."
        print(f"[ERROR] {error_message}")
        notify_failure(error_message)
        return {"statusCode": 500, "body": error_message}

    # Get values from Lambda invokation event
    runInstanceName = event.get("runInstanceName",'')
    runCounterFromEvent = event.get("runCounter",'')
    processComplete = event.get("processComplete", 0)

    # Check if this is the first run.
    if runInstanceName == '':
        # This is the first run. Get networks. 
        print("[INFO] Fetching network list...")

        networkList = []
        nextToken = None

        while True:
            networks, nextToken = merakiAPInetworkList(authToken, nextToken)
            if networks is None:
                error_message = "API is unreachable or returned no data. Aborting process."
                print(f"[ERROR] {error_message}")
                notify_failure(error_message)
                return {"statusCode": 500, "body": error_message}

            for network in networks:
                device_data = {
                    "networkID": network.get("id"),
                    "networkName": network.get("name"),
                    "restaurant_number": extract_restaurant_number(network.get("name", "")),
                }
                networkList.append(device_data)

            if not nextToken:
                print("[SUCCESS] All networks retrieved.")
                break

        #Invoke Lambda to retrive client information, then exit function.
        invokeFunctionAgain(
            runCount=0, 
            startIndex=0, 
            networkList=networkList, 
            clientList=[], 
            runInstanceName=datetime.now(ZoneInfo("Europe/London")).strftime('%Y-%m-%d_%H-%M-%S'),
            functionName=context.function_name
            )
        return


    elif processComplete==0:
        # This is not the first run and process is not complete. Get clients.

        # Retrive temporary client list file from S3 location.
        try:
            jsonFile = s3.get_object(Bucket=TEMP_FILE_LOCATION_BUCKET_NAME, Key=f"{TEMP_FILE_LOCATION_OBJECT_KEY}meraki-client-temp-data.json")
            jsonContent = jsonFile['Body'].read().decode('utf-8')
            data = json.loads(jsonContent)

            clientList = []
            networkList = data.get('networkList', [])
            runCounter = data.get('runCounter', maxRuns)
            startIndex = data.get('startIndex', 0)

            print(f"[INFO] Retrieved temporary data file from S3 location. Run Instance: {runInstanceName}.")
            print(f"[INFO] Network List contains {len(networkList)} items | Networks to query every run: {networkPerRun}") 
        except:
            error_message = "Could not fetch temporary client list file from S3 location."
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        # Check run count from temporaty data file matches event data
        if runCounter != runCounterFromEvent:
            error_message = f"Run count from Lambda invokation ({runCounter}) does not match temporary data file ({runCounterFromEvent})."
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        # Check maximum function invokations is not exceeded 
        print(f"[INFO] Runs Completed: {runCounter} | Maximum runs allowed: {maxRuns}")
        if runCounter >= maxRuns:
            error_message = "Maximum runs exceeded."
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        # Check network list is populated
        if len(networkList) == 0:
            error_message = "No networks in network list."
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        # Calculate index of network list to fetch
        endIndex = (startIndex + networkPerRun) - 1
        if endIndex >= len(networkList):
            endIndex = len(networkList) - 1

        print(f"[INFO] Network range to fetch: {startIndex} - {endIndex}")

        nextToken = None

        # Loop through range in network list to get clients
        #for network in networkList[startIndex:endIndex]:
        while (startIndex <= endIndex) and (context.get_remaining_time_in_millis() > minimumRemainingTime):
            while True:
                network = networkList[startIndex]
                clients, nextToken = merakiAPIclientList(authToken, nextToken, network["networkID"])
                if clients is None:
                    error_message = "API is unreachable or returned no data. Aborting process."
                    print(f"[ERROR] {error_message}")
                    notify_failure(error_message)
                    return {"statusCode": 500, "body": error_message}

                for client in clients:
                    device_data = {
                        "restaurant_number": network["restaurant_number"],
                        "networkName": network["networkName"],
                        "id": client.get("id"),
                        "mac": client.get("mac"),
                        "description": client.get("description"),
                        "ip": client.get("ip"),
                        "ip6": client.get("ip6"),
                        "ip6Local": client.get("ip6Local"),
                        "user": client.get("user"),
                        "firstSeen": client.get("firstSeen"),
                        "lastSeen": client.get("lastSeen"),
                        "manufacturer": client.get("manufacturer"),
                        "os": client.get("os"),
                        "deviceTypePrediction": client.get("deviceTypePrediction"),
                        "recentDeviceSerial": client.get("recentDeviceSerial"),
                        "recentDeviceName": client.get("recentDeviceName"),
                        "recentDeviceMac": client.get("recentDeviceMac"),
                        "recentDeviceConnection": client.get("recentDeviceConnection"),
                        "ssid": client.get("ssid"),
                        "vlan": client.get("vlan"),
                        "switchport": client.get("switchport"),
                        "usage": client.get("usage"),
                        "status": client.get("status"),
                        "notes": client.get("notes"),
                        "groupPolicy8021x": client.get("groupPolicy8021x"),
                        "adaptivePolicyGroup": client.get("adaptivePolicyGroup"),
                        "smInstalled": client.get("smInstalled"),
                        "pskGroup": client.get("pskGroup"),
                        "wirelessCapabilities": client.get("wirelessCapabilities"),
                        "mcgSerial": client.get("mcgSerial"),
                        "mcgNodeName": client.get("mcgNodeName"),
                        "mcgNodeMac": client.get("mcgNodeMac"),
                        "mcgNetworkId": client.get("mcgNetworkId"),
                        "sys_updated_timestamp": datetime.now().isoformat()
                    }
                    clientList.append(device_data)

                if not nextToken:    
                    break

            startIndex+=1

        if context.get_remaining_time_in_millis() < minimumRemainingTime:
            print(F"[INFO] Less than {minimumRemainingTime/1000} seconds ramining for Lambda. Restarting.")
        else:
            print("[INFO] Maximum number of networks queried.")

        # Export client list to S3 location
        exportPayload(clientList=clientList, runInstanceName=runInstanceName, partNo=runCounter+1)

        # Check if all network have been queried.
        if startIndex < len(networkList):
            # Invoke Lambda to retrive client information
            invokeFunctionAgain(
                runCount=runCounter+1, 
                startIndex=startIndex, 
                networkList=networkList, 
                clientList=clientList, 
                runInstanceName=runInstanceName, 
                functionName=context.function_name
                )
            return
    
        else:
            print("[SUCCESS] All clients retrived.")

            # Invoke lambda to murge JSON files.
            print("[INFO] Calling Lambda murge JSON files.")
            payload = {
                "runInstanceName": runInstanceName,
                "processComplete": 1
                }
            client = boto3.client('lambda')
            response = client.invoke(
                FunctionName=context.function_name, 
                InvocationType='Event',
                Payload=json.dumps(payload).encode('utf-8')
            )
            if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 202:
                print("[INFO] Called Lambda successfully.")
            else:
                error_message = f"Failed to call Lamdba: {response}."
                print(f"[ERROR] {error_message}")
                notify_failure(error_message)
            return

    else:
        # Process is complete. Combine files. 
        print(f"[INFO] Combine JSON files for run instance: {runInstanceName}.")

        # Find JSON files for this run
        fileKeys = []
        try:
            paginator = s3.get_paginator('list_objects_v2')
            files = paginator.paginate(Bucket=TEMP_FILE_LOCATION_BUCKET_NAME, Prefix=f"meraki/client_info/client-list-{runInstanceName}-part")
            for file in files:
                for obj in file.get('Contents', []):
                    fileKeys.append(obj['Key'])

            print(f"[INFO] Found {len(fileKeys)} files: {fileKeys}")
        except Exception as e:
            error_message = f"Could not find JSON files: {e}"
            print(f"[ERROR] {error_message}")
            notify_failure(error_message)
            return {"statusCode": 500, "body": error_message}

        # Load and combine JSON files
        print("[INFO] Loading JSON files...")
        combined_data = []
        for key in fileKeys:
            try:
                print(f"[INFO] Loading {key}...")
                response = s3.get_object(Bucket=TEMP_FILE_LOCATION_BUCKET_NAME, Key=key)
                content = response['Body'].read()
                data = json.loads(content)
                if isinstance(data, list):
                    combined_data.extend(data)
                    print(f"[INFO] Loaded {key}.")
                else:
                    print(f"[WARNING] {key} does not contain a JSON array.")
            except Exception as e:
                error_message = f"Could not read {key}: {e}"
                print(f"[ERROR] {error_message}")
                notify_failure(error_message)
                return {"statusCode": 500, "body": error_message}

        print("[INFO] All JSON files retrieved.")

        # Save the combined data
        json_data = json.dumps(combined_data, indent=4)
        s3_key = f"{OUTPUT_KEY}client-list-{runInstanceName}_combined.json"

        exportFileToS3(bucket=OUTPUT_BUCKET, key=s3_key, body=json_data)

        return
