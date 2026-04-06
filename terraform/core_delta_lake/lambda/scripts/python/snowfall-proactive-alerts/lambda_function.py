import boto3
import html
import json
import os
import time
import uuid
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

# =============================
# Secrets Manager (SMTP)
# =============================

SECRET_NAME = "uk-snowfall"
REGION_NAME = "eu-central-1"

def get_smtp_credentials():
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        resp = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(resp["SecretString"])

        username = secret.get("uk-snowfall-proactive-smpt-api-key")
        password = secret.get("uk-snowfall-proactive-smpt-secret-key")

        if not username or not password:
            print("[ERROR] Missing SMTP credentials in Secrets Manager.")
            return None, None

        return username, password

    except Exception as e:
        print(f"[ERROR] Failed to retrieve SMTP secrets: {e}")
        return None, None

# =============================
# Environment
# =============================

RULES_TABLE = os.environ["RULES_TABLE"]
TICKETS_TABLE = os.environ["TICKETS_TABLE"]
CONNECTIONS_TABLE = os.environ["TABLE_NAME"]
ATHENA_OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]
STAGE_NAME = os.environ["STAGE_NAME"]

SMTP_SERVER = "in.mailjet.com"
SMTP_PORT = 587
SMTP_SENDER = "snowfall-proactive-alerts@ext.mcdonalds.com"

# Single-table discriminator values for the shared tickets table.
RECORD_TYPE_EMAIL_ALERT = "EMAIL_ALERT"
RECORD_TYPE_SERVICENOW_CASE = "SERVICENOW_CASE"

SMTP_USERNAME, SMTP_PASSWORD = get_smtp_credentials()

# =============================
# AWS Clients
# =============================

dynamodb = boto3.resource("dynamodb")

rules_table = dynamodb.Table(RULES_TABLE)
tickets_table = dynamodb.Table(TICKETS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)

athena = boto3.client("athena")

# =============================
# Lambda Entry
# =============================

def lambda_handler(event, context):

    print("Starting rule execution")

    rules = scan_all_items(rules_table)

    for rule in rules:

        if not rule.get("active"):
            continue

        print(f"Evaluating rule {rule['rule_id']}")

        records = run_athena(rule["query"])

        if not records:
            continue

        process_rule(rule, records)

    return {"status": "completed"}

# =============================
# Athena Query
# =============================

def run_athena(query):

    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": "uk_snowfall_processed"},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_S3},
    )

    execution_id = response["QueryExecutionId"]

    while True:

        result = athena.get_query_execution(QueryExecutionId=execution_id)
        state = result["QueryExecution"]["Status"]["State"]

        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break

        time.sleep(2)

    if state != "SUCCEEDED":
        return []

    records = []

    next_token = None
    skip_header = True

    while True:

        query_args = {"QueryExecutionId": execution_id}
        if next_token:
            query_args["NextToken"] = next_token

        results = athena.get_query_results(**query_args)
        rows = results["ResultSet"]["Rows"]

        for row in rows:

            if skip_header:
                skip_header = False
                continue

            data = row["Data"]

            # Support both formats:
            # 1 column -> message only (global rule)
            # 2 columns -> restaurant + message
            if len(data) == 1:
                records.append({
                    "restaurant_number": None,
                    "message": data[0].get("VarCharValue", "")
                })
            else:
                records.append({
                    "restaurant_number": data[0].get("VarCharValue", ""),
                    "message": data[1].get("VarCharValue", "")
                })

        next_token = results.get("NextToken")
        if not next_token:
            break

    return records

# =============================
# Rule Processing
# =============================

def process_rule(rule, records):

    # Only valid restaurant values
    restaurants = get_unique_restaurants(records)

    script_output = None

    # STEP 1 Proactive Script (ONLY if restaurant exists)
    if rule.get("proactive_script") and restaurants:

        script_output = run_proactive_script(
            restaurants[0],
            rule["proactive_script_name"]
        )

        if script_output.get("remediated"):
            print("Issue remediated by script")
            return

    # STEP 2 Cooldown Check
    if rule.get("email_alert"):

        if not should_send_alert(rule, restaurants):
            print("Cooldown active. Skipping alert.")
            return

    # STEP 3 Send Email
    if rule.get("email_alert"):

        if send_email(rule, records, script_output):
            record_email_alert(rule, records)

# =============================
# Cooldown Logic
# =============================

def should_send_alert(rule, restaurants):

    cooldown_hours = get_cooldown_hours(rule)

    if cooldown_hours <= 0:
        return True

    items = scan_all_items(
        tickets_table,
        Attr("rule_id").eq(rule["rule_id"]) & Attr("record_type").eq(RECORD_TYPE_EMAIL_ALERT)
    )

    if not items:
        return True

    last_ticket = max(items, key=alert_sort_key)

    last_restaurants = set(last_ticket.get("violating_restaurants", []))
    current_restaurants = set(restaurants)

    last_time_str = last_ticket.get("last_alert_time")

    last_time = datetime.fromisoformat(last_time_str) if last_time_str else None
    now = datetime.now(ZoneInfo("Europe/London"))

    # If no restaurant rules → always allow based on cooldown only
    if not restaurants:
        if last_time:
            elapsed = (now - last_time).total_seconds() / 3600
            return elapsed >= cooldown_hours
        return True

    if not current_restaurants.issubset(last_restaurants):
        print("New restaurant detected")
        return True

    if last_time:

        elapsed = (now - last_time).total_seconds() / 3600

        if elapsed >= cooldown_hours:
            print("Cooldown expired")
            return True

    return False

# =============================
# Alert History
# =============================

def scan_all_items(table, filter_expression=None):

    scan_kwargs = {}
    if filter_expression is not None:
        scan_kwargs["FilterExpression"] = filter_expression

    items = []
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))

    while response.get("LastEvaluatedKey"):
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    return items

def get_unique_restaurants(records):

    restaurants = []
    seen = set()

    for record in records:
        restaurant_number = record.get("restaurant_number")
        if restaurant_number and restaurant_number not in seen:
            seen.add(restaurant_number)
            restaurants.append(restaurant_number)

    return restaurants

def parse_alert_time(timestamp_value):

    if not timestamp_value:
        return None

    try:
        return datetime.fromisoformat(timestamp_value)
    except ValueError:
        return None

def get_cooldown_hours(rule):

    raw_value = rule.get("email_cooldown_hours") or 0

    try:
        return max(int(raw_value), 0)
    except (TypeError, ValueError):
        print(
            f"Invalid cooldown value for rule {rule['rule_id']}: {raw_value}. Defaulting to 0."
        )
        return 0

def get_rule_email_recipients(rule):

    recipient_value = str(rule.get("email_dl") or "")

    seen = set()
    recipients = []

    for email in recipient_value.replace(";", ",").split(","):
        normalized_email = email.strip()

        if not normalized_email:
            continue

        dedupe_key = normalized_email.lower()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        recipients.append(normalized_email)

    return recipients

def alert_sort_key(item):

    parsed_time = parse_alert_time(item.get("last_alert_time"))
    if not parsed_time:
        return float("-inf")

    return parsed_time.timestamp()

def record_email_alert(rule, records):

    restaurants = get_unique_restaurants(records)

    first_record = records[0]

    alert_id = f"EMAIL#{uuid.uuid4()}"

    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
    recipients = get_rule_email_recipients(rule)

    item = {
        "ticket_id": alert_id,
        "record_type": RECORD_TYPE_EMAIL_ALERT,
        "rule_id": rule["rule_id"],
        "restaurant_number": first_record.get("restaurant_number"),
        "message": first_record["message"],
        "status": "SENT",
        "created_at": timestamp,
        "violating_restaurants": restaurants,
        "last_alert_time": timestamp,
        "email_recipients": ", ".join(recipients),
    }

    tickets_table.put_item(Item=item)

    print(f"Email alert recorded: {alert_id}")

# =============================
# Email (SMTP - Mailjet)
# =============================

def send_email(rule, records, script_output):

    subject = f"{rule['incident_description']} - [{len(records)} Alerts]"
    recipients = get_rule_email_recipients(rule)

    if not recipients:
        print(f"Email send failed: no email_dl configured for rule {rule['rule_id']}")
        return False

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Email send failed: SMTP credentials are unavailable")
        return False

    has_restaurant = any(r.get("restaurant_number") for r in records)
    cooldown_hours = get_cooldown_hours(rule)

    html_body_template = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; color: #1f2937; }
            .container { max-width: 860px; margin: 0 auto; padding: 20px; }
            .title { font-size: 22px; font-weight: bold; margin-bottom: 8px; }
            .subtitle { color: #4b5563; margin-bottom: 18px; }
            .meta { background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; }
            .meta p { margin: 6px 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 12px; }
            th { background: #111827; color: #ffffff; text-align: left; padding: 10px; }
            td { border-bottom: 1px solid #e5e7eb; padding: 10px; vertical-align: top; }
            .section-title { margin-top: 22px; margin-bottom: 10px; font-size: 16px; font-weight: bold; }
            pre { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; white-space: pre-wrap; }
        </style>
    </head>
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Email send failed: SMTP credentials are unavailable")
        return False
    <body>
        <div class="container">
            <div class="title">Proactive Alert</div>
            <div class="subtitle">Violations detected for a Snowfall proactive rule.</div>
            <div class="meta">
                <p><strong>Rule:</strong> {incident_description}</p>
                <p><strong>Violations:</strong> {violation_count}</p>
                <p><strong>Cooldown:</strong> {cooldown_label}</p>
            </div>
            <div class="section-title">Violation Details</div>
            <table>
                <tr>
                    <th>S.No</th>
                    {restaurant_header}
                    <th>Message</th>
                </tr>
                {rows}
            </table>
            {script_section}
        </div>
    </body>
    </html>
    """

    rows = []
    for i, record in enumerate(records, start=1):
        cells = [f"<td>{i}</td>"]

        if has_restaurant:
            cells.append(f"<td>{html.escape(str(record.get('restaurant_number', '')))}</td>")

        cells.append(f"<td>{html.escape(str(record['message']))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    script_section = ""
    if script_output:
        script_section = """
        <div class="section-title">Additional Proactive Measures</div>
        <p>Proactive script execution was attempted for this rule.</p>
        <pre>{script_output}</pre>
        """.format(script_output=html.escape(json.dumps(script_output, indent=2)))

    html_body = html_body_template.format(
        incident_description=html.escape(str(rule["incident_description"])),
        violation_count=len(records),
        cooldown_label=f"{cooldown_hours} hour(s)" if cooldown_hours > 0 else "No cooldown",
        restaurant_header="<th>Restaurant</th>" if has_restaurant else "",
        rows="".join(rows),
        script_section=script_section,
    )

    try:

        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject
        msg["From"] = SMTP_SENDER
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(SMTP_USERNAME, SMTP_PASSWORD)

            server.sendmail(
                SMTP_SENDER,
                recipients,
                msg.as_string(),
            )

        print("Email sent successfully via Mailjet")
        return True

    except Exception as e:

        print(f"Email send failed: {str(e)}")
        return False

# =============================
# WebSocket Proactive Script
# =============================

def run_proactive_script(restaurant_number, script_name):

    print(f"Triggering script {script_name}")

    if STAGE_NAME == "prod":
        endpoint = "https://j3v4n25iwa.execute-api.eu-central-1.amazonaws.com/prod/"
    elif STAGE_NAME == "nprod":
        endpoint = "https://egnv9vgjjh.execute-api.eu-central-1.amazonaws.com/nprod/"
    else:
        endpoint = "https://vugx1b0qef.execute-api.eu-central-1.amazonaws.com/dev/"

    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)

    response = connections_table.scan(
        FilterExpression=Attr("restaurant_number").eq(str(restaurant_number))
        & Attr("status").eq("connected")
    )

    for item in response["Items"]:

        message = {
            "command_id": str(uuid.uuid4()),
            "script_name": script_name,
            "action": "trigger_script",
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:

            apigw.post_to_connection(
                ConnectionId=item["connectionId"],
                Data=json.dumps(message).encode(),
            )

        except ClientError:
            pass

    return {
        "status": "triggered",
        "remediated": False
    }