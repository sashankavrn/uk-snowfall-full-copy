import boto3
import os
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

dynamodb = boto3.client("dynamodb")
RULES_TABLE = os.environ["RULES_TABLE"]

def find_existing_rule(incident_desc, metric):
    print("Searching for existing rule by incident_description + metric")

    response = dynamodb.scan(
        TableName=RULES_TABLE,
        FilterExpression="incident_description = :i AND metric = :m",
        ExpressionAttributeValues={
            ":i": {"S": incident_desc},
            ":m": {"S": metric}
        }
    )

    if response.get("Items"):
        rule = response["Items"][0]
        print(f"Existing rule found → rule_id = {rule['rule_id']['S']}")
        return rule  # return full rule

    print("No existing rule found.")
    return None

def create_rule(rule_item):
    print("Creating new rule...")

    rule_id = str(uuid.uuid4())
    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()

    rule_item["rule_id"] = {"S": rule_id}
    rule_item["created_at"] = {"S": timestamp}

    dynamodb.put_item(
        TableName=RULES_TABLE,
        Item=rule_item
    )

    print(f"Rule created with rule_id = {rule_id}")
    return {"message": "Rule created", "rule_id": rule_id}

def update_rule(existing_rule_id, rule_item):
    print(f"Updating rule: {existing_rule_id}")

    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()

    update_expr_parts = ["updated_at = :updated_at"]
    expr_vals = {":updated_at": {"S": timestamp}}
    expr_names = {}

    for key, val in rule_item.items():
        if key == "rule_id":  # cannot update PK
            continue

        expr_name = f"#{key}"
        expr_val = f":{key}"

        update_expr_parts.append(f"{expr_name} = {expr_val}")
        expr_names[expr_name] = key
        expr_vals[expr_val] = val

    update_expression = "SET " + ", ".join(update_expr_parts)

    response = dynamodb.update_item(
        TableName=RULES_TABLE,
        Key={"rule_id": {"S": existing_rule_id}},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_vals,
        ReturnValues="ALL_NEW"
    )

    print("Rule updated successfully")
    return {"message": "Rule updated", "rule_id": existing_rule_id}

def lambda_handler(event, context):
    print("Lambda invoked with event:")
    print(event)

    # Event contains DynamoDB-format fields except rule_id
    incident_desc = event["incident_description"]["S"]
    metric = event["metric"]["S"]

    existing = find_existing_rule(incident_desc, metric)

    if existing:
        existing_rule_id = existing["rule_id"]["S"]
        return update_rule(existing_rule_id, event)

    return create_rule(event)