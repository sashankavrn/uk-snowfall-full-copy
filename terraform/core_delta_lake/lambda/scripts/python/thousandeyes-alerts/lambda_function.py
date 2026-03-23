import json
import boto3
import os
import time
import re
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def lambda_handler(event, context):
    try:
        # ----------------------------------------------------
        # LOG EVERYTHING FOR DEBUGGING
        # ----------------------------------------------------
        print("=== EVENT RECEIVED ===")
        print(json.dumps(event))

        body = event.get("body")
        print("=== RAW BODY RECEIVED ===")
        print(body)

        # Parse JSON body
        payload = json.loads(body) if isinstance(body, str) else body

        print("=== PARSED PAYLOAD ===")
        print(json.dumps(payload))

        # ----------------------------------------------------
        # EXTRACT RESTAURANT NUMBER
        # ----------------------------------------------------
        agent = payload.get("agent", {})
        agent_name = agent.get("agentName", "")

        restaurant_number = extract_restaurant_number(agent_name)

        if restaurant_number is None:
            raise ValueError(f"Could not extract restaurant_number from agentName: {agent_name}")

        # ----------------------------------------------------
        # EXTRACT ALERT FIELDS
        # ----------------------------------------------------
        alert = payload.get("alert", {})
        alert_id = str(alert.get("alertId", f"unknown-{int(time.time())}"))

        timestamp_epoch = payload.get("timestamp", int(time.time()))
        timestamp_iso = datetime.utcfromtimestamp(timestamp_epoch).isoformat()

        # ----------------------------------------------------
        # VIOLATIONS (SAFE DECIMAL)
        # ----------------------------------------------------
        violations = payload.get("violations", [])
        violation_summary = [
            {
                "metric": v.get("metric"),
                "value": safe_decimal(v.get("value")),
                "threshold": safe_decimal(v.get("threshold"))
            }
            for v in violations
        ]

        # ----------------------------------------------------
        # TTL (7 days)
        # ----------------------------------------------------
        ttl = int(time.time()) + (7 * 24 * 60 * 60)

        # ----------------------------------------------------
        # BUILD DYNAMODB ITEM
        # ----------------------------------------------------
        item = {
            "restaurant_number": restaurant_number,  # REQUIRED PK
            "alert_id": alert_id,                    # REQUIRED SK

            "timestamp_iso": timestamp_iso,
            "timestamp_epoch": timestamp_epoch,

            "event_type": payload.get("eventType", "UNKNOWN"),

            "alert_name": alert.get("alertName", "UNKNOWN"),
            "severity": alert.get("severity", "UNKNOWN"),
            "state": alert.get("state", "UNKNOWN"),

            "test_id": str(payload.get("test", {}).get("testId", "UNKNOWN")),
            "test_name": payload.get("test", {}).get("testName", "UNKNOWN"),

            "agent_id": str(agent.get("agentId", "UNKNOWN")),
            "agent_name": agent_name,

            "violations": violation_summary,
            "raw_payload": payload,

            "ttl": ttl
        }

        print("=== FINAL ITEM TO WRITE ===")
        print(json.dumps(item, default=str))

        # ----------------------------------------------------
        # WRITE TO DYNAMODB
        # ----------------------------------------------------
        table.put_item(Item=item)

        return response(200, "Stored successfully")

    except Exception as e:
        print("ERROR:", str(e))
        return response(500, str(e))


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def extract_restaurant_number(agent_name: str):
    """
    Extracts the restaurant number from agentName.
    Example: "Restaurant-2043-London" → 2043
    """
    match = re.search(r"(\d+)", agent_name)
    return int(match.group(1)) if match else None


def safe_decimal(value):
    """Convert floats to Decimal for DynamoDB."""
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def response(code, msg):
    return {
        "statusCode": code,
        "body": json.dumps({"message": msg})
    }
