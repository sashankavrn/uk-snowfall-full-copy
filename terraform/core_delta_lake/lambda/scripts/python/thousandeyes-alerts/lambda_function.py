import base64
import json
import os
import re
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def _epoch_ms_to_iso(epoch_ms):
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_restaurant_number(source_name):
    if not source_name:
        return None
    match = re.search(r"UK(\d{4,6})", source_name, re.IGNORECASE)
    return match.group(1) if match else None


def lambda_handler(event, context):
    try:
        print("=== FULL EVENT ===")
        print(json.dumps(event, indent=2))

        body = event.get("body") or ""

        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        print("=== RAW BODY ===")
        print(body)

        payload = json.loads(body) if isinstance(body, str) else body

        print("=== PARSED PAYLOAD ===")
        print(json.dumps(payload, indent=2))

        if not isinstance(payload, dict):
            return response(400, "Invalid payload")

        alert = payload.get("alert", {})

        is_cleared = alert.get("cleared") is not None

        # TODO: uncomment full schema when real alerts are configured
        item = {
            "alert_id":           alert.get("id"),
            "created_at":         datetime.utcnow().isoformat(),
            # "te_event_id":        payload.get("id"),
            # "event_type":         payload.get("type"),
            # "alert_type":         alert.get("type"),
            # "severity":           alert.get("severity"),
            # "test_name":          (alert.get("test") or {}).get("name"),
            # "rule_id":            (alert.get("rule") or {}).get("id"),
            # "rule_name":          (alert.get("rule") or {}).get("name"),
            # "rule_expression":    (alert.get("rule") or {}).get("expression"),
            # "targets":            alert.get("targets", []),
            # "sources":            [...],
            # "restaurant_number":  restaurant_number,
            # "triggered_at":       _epoch_ms_to_iso(alert.get("triggered")),
            # "cleared_at":         _epoch_ms_to_iso(alert.get("cleared")),
            # "is_cleared":         is_cleared,
            # "snow_case_sys_id":   None,
            # "snow_case_number":   None,
            # "snow_create_status": "PENDING",
        }

        print("=== DYNAMODB ITEM ===")
        print(json.dumps(item, indent=2, default=str))

        table.put_item(Item=item)

        print(f"Successfully stored alert_id: {item['alert_id']}")

        return response(200, {
            "message": "Stored successfully",
            "alert_id": item["alert_id"],
        })

    except Exception as e:
        print("ERROR OCCURRED")
        print(str(e))
        return response(500, "Internal server error")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
    }