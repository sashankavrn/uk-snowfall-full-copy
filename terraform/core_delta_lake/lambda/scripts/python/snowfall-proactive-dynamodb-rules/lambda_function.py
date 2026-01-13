
import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

dynamodb = boto3.client("dynamodb")
RULES_TABLE = os.environ["RULES_TABLE"]
NUM_RULES = int(os.environ.get("NUM_RULES", "10"))   # number of rules to create


def get_existing_rule_ids():
    """Return all existing rule_id values as a set of strings."""
    response = dynamodb.scan(TableName=RULES_TABLE, ProjectionExpression="rule_id")

    rule_ids = {item["rule_id"]["S"] for item in response.get("Items", [])}

    # Handle paginated scans
    while "LastEvaluatedKey" in response:
        response = dynamodb.scan(
            TableName=RULES_TABLE,
            ProjectionExpression="rule_id",
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        rule_ids.update(item["rule_id"]["S"] for item in response.get("Items", []))

    return rule_ids


def build_rule_item(i):
    """Build a placeholder rule item for rule i."""
    created_at = datetime.now(ZoneInfo("Europe/London")).isoformat()

    return {
        "rule_id": {"S": str(i)},
        "active": {"BOOL": True},
        "created_at": {"S": created_at},
        "incident_description": {"S": f"your rule {i} incident description"},
        "query": {"S": f"your rule {i} query"},
        "email_alert": {"BOOL": True},
        "servicenow_alert": {"BOOL": True},
        "proactive_script": {"BOOL": True},
        "email_dl": {"S": f"your rule {i} email_dl"},
        "proactive_script_name": {"S": f"your rule {i} proactive_script_name"}
    }


def create_rule(item):
    dynamodb.put_item(TableName=RULES_TABLE, Item=item)
    print(f"Created rule_id {item['rule_id']['S']}")


def lambda_handler(event, context):
    print(f"NUM_RULES configured = {NUM_RULES}")

    existing_ids = get_existing_rule_ids()
    print(f"Existing rule_ids in DB → {existing_ids}")

    created = []
    skipped = []

    for i in range(1, NUM_RULES + 1):
        rule_id = str(i)

        if rule_id in existing_ids:
            skipped.append(rule_id)
            continue

        # Create missing rules
        rule_item = build_rule_item(i)
        create_rule(rule_item)
        created.append(rule_id)

    print("Completed rule initialization")

    return {
        "message": "Rule initialization complete",
        "created_rule_ids": created,
        "skipped_existing_rule_ids": skipped,
        "total_required_rules": NUM_RULES
    }