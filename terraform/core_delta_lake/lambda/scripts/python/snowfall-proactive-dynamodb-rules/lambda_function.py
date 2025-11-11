import boto3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb', region_name=os.environ['DYNAMO_REGION'])
    table_name = os.environ['RULES_TABLE']

    # Timestamp for audit
    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
    print(f"[INFO] Lambda execution started at {timestamp}")

    query = """WITH res as (
    SELECT DISTINCT "restaurant_number"
    FROM "uk_snowfall_processed"."newrelic_digital_3po_foe_response"
    WHERE cdc_timestamp = (SELECT max(cdc_timestamp) FROM "uk_snowfall_processed"."newrelic_digital_3po_foe_response")
),
ordcnt as (
    SELECT
        "restaurant_number",
        "foe_response",   
        "3po_response",
        "3po_description",
        sum("count") "count"
    FROM "uk_snowfall_processed"."newrelic_digital_3po_foe_response"
    WHERE 
        cdc_timestamp = (SELECT max(cdc_timestamp) FROM "uk_snowfall_processed"."newrelic_digital_3po_foe_response")
        and "3po_description" != 'Auto release is disabled for store'
    GROUP BY 
        "restaurant_number",
        "foe_response",   
        "3po_response",
        "3po_description"
    ORDER BY "count" DESC
),
toperr as (
    SELECT 
        "restaurant_number",
        'Top error: FOE Error ' || cast("foe_response" as varchar) || ' | 3PO Error ' || cast("3po_response" as varchar) || ' ' || "3po_description" "message"
    FROM (
        SELECT 
            *,
            ROW_NUMBER() OVER (PARTITION BY restaurant_number ORDER BY "count" DESC) "rn"
        FROM ordcnt
        WHERE 
            (foe_response != 0 OR "3po_response" != 1)
            and "3po_description" != 'Auto release is disabled for store'
    )
    WHERE rn = 1
),
errcnt as (
    SELECT 
        *,
        cast(error_count as double) / order_count "error_percentage"
    FROM (
        SELECT 
            res.restaurant_number,
            (
                SELECT sum("count") 
                FROM ordcnt 
                WHERE ordcnt.restaurant_number = res.restaurant_number
            ) "order_count",
            (
                SELECT sum("count") 
                FROM ordcnt 
                WHERE 
                    ordcnt.restaurant_number = res.restaurant_number
                    and ("foe_response" != 0 or "3po_response" != 1)
            ) "error_count"
        FROM res
    )
)
SELECT 
    errcnt.restaurant_number,
    '[PROACTIVE] 3PO Error Rate ' || cast(round(error_percentage * 100, 0) as varchar) || '% | ' || toperr.message "message"
FROM errcnt 
LEFT JOIN toperr ON
    toperr.restaurant_number = errcnt.restaurant_number
WHERE error_percentage > 0.6
ORDER BY error_percentage DESC
    """

    rule_item = {
        'rule_id':              {'S': '9'},
        'active':               {'BOOL': True},
        'query':                {'S': query},
        'database':             {'S': 'uk_snowfall_processed'},
        'threshold':            {'S': '95'},
        'incident_description': {'S': 'test - Disk usage above 90%'},
        'metric':               {'S': 'average_disk_used_percent'},
        'created_at':           {'S': timestamp}
    }

    dynamodb.put_item(TableName=table_name, Item=rule_item)

    print(f"[INFO] Rule inserted at {timestamp}")
    return {
        'statusCode': 200,
        'body': 'Rule inserted successfully'
    }
