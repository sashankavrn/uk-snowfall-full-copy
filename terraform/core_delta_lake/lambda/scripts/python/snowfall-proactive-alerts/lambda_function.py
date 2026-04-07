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
PROACTIVE_ALERTS_TABLE = os.environ["PROACTIVE_ALERTS_TABLE"]
CONNECTIONS_TABLE = os.environ["TABLE_NAME"]
RESULTS_TABLE_NAME = os.environ.get("RESULTS_TABLE_NAME", "")
ATHENA_OUTPUT_S3 = os.environ["ATHENA_OUTPUT_S3"]
STAGE_NAME = os.environ["STAGE_NAME"]

SMTP_SERVER = "in.mailjet.com"
SMTP_PORT = 587
SMTP_SENDER = "snowfall-proactive-alerts@ext.mcdonalds.com"

RECORD_TYPE_EMAIL_ALERT = "EMAIL_ALERT"
RECORD_TYPE_SERVICENOW_CASE = "SERVICENOW_CASE"

SMTP_USERNAME, SMTP_PASSWORD = get_smtp_credentials()

# =============================
# AWS Clients
# =============================

dynamodb = boto3.resource("dynamodb")

rules_table = dynamodb.Table(RULES_TABLE)
proactive_alerts_table = dynamodb.Table(PROACTIVE_ALERTS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)
results_table = dynamodb.Table(RESULTS_TABLE_NAME) if RESULTS_TABLE_NAME else None

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

    script_results = []

    # STEP 1 Proactive Script (ONLY if restaurant exists)
    if rule.get("proactive_script") and restaurants:

        all_triggered = []

        for restaurant in restaurants:
            triggered = run_proactive_script(restaurant, rule["proactive_script_name"])
            all_triggered.extend(triggered)

        if all_triggered:
            print(f"Polling results for {len(all_triggered)} triggered script(s)")
            script_results = poll_script_results(all_triggered)

    # STEP 2 Cooldown Check (always applies)
    if not should_send_alert(rule, restaurants):
        print("Cooldown active. Skipping alert.")
        return

    # STEP 3 Send Email (only if email_alert is enabled)
    email_sent = False
    if rule.get("email_alert"):
        email_sent = send_email(rule, records, script_results)

    # STEP 4 Record alert (always, regardless of email_alert flag)
    record_email_alert(rule, records, email_sent=email_sent)

# =============================
# Cooldown Logic
# =============================

def should_send_alert(rule, restaurants):

    cooldown_hours = get_cooldown_hours(rule)

    if cooldown_hours <= 0:
        return True

    items = scan_all_items(
        proactive_alerts_table,
        Attr("rule_id").eq(rule["rule_id"]) & Attr("record_type").eq(RECORD_TYPE_EMAIL_ALERT)
    )

    if not items:
        return True

    last_ticket = max(items, key=alert_sort_key)

    last_restaurants = set(last_ticket.get("violating_restaurants", []))
    current_restaurants = set(restaurants)

    last_time_str = last_ticket.get("last_alert_time")

    last_time = parse_alert_time(last_time_str)
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
        return max(float(raw_value), 0.0)
    except (TypeError, ValueError):
        print(
            f"Invalid cooldown value for rule {rule['rule_id']}: {raw_value}. Defaulting to 0."
        )
        return 0.0

def format_cooldown_label(cooldown_hours):

    if cooldown_hours <= 0:
        return "No cooldown"

    total_minutes = cooldown_hours * 60

    if total_minutes < 60:
        return f"{total_minutes:g} minute(s)"

    return f"{cooldown_hours:g} hour(s)"

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

def record_email_alert(rule, records, email_sent=True):

    restaurants = get_unique_restaurants(records)

    first_record = records[0]

    alert_id = f"ALERT#{uuid.uuid4()}"

    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()
    recipients = get_rule_email_recipients(rule)

    item = {
        "alert_id": alert_id,
        "record_type": RECORD_TYPE_EMAIL_ALERT,
        "rule_id": rule["rule_id"],
        "restaurant_number": first_record.get("restaurant_number"),
        "message": first_record["message"],
        "status": "SENT" if email_sent else "RECORDED",
        "created_at": timestamp,
        "violating_restaurants": restaurants,
        "last_alert_time": timestamp,
        "email_recipients": ", ".join(recipients),
    }

    proactive_alerts_table.put_item(Item=item)

    print(f"Alert recorded: {alert_id} (status: {'SENT' if email_sent else 'RECORDED'})")

# =============================
# Email (SMTP - Mailjet)
# =============================

def send_email(rule, records, script_results):

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
            body {{ font-family: Arial, sans-serif; color: #1f2937; }}
            .container {{ max-width: 860px; margin: 0 auto; padding: 20px; }}
            .title {{ font-size: 22px; font-weight: bold; margin-bottom: 8px; }}
            .subtitle {{ color: #4b5563; margin-bottom: 18px; }}
            .meta {{ background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; }}
            .meta p {{ margin: 6px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
            th {{ background: #111827; color: #ffffff; text-align: left; padding: 10px; }}
            td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; vertical-align: top; }}
            .section-title {{ margin-top: 22px; margin-bottom: 10px; font-size: 16px; font-weight: bold; }}
            pre {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; white-space: pre-wrap; }}
        </style>
    </head>
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
    if script_results:
        result_rows = ""
        for r in script_results:
            status = r.get("execution_status", "unknown")
            color = "#16a34a" if status == "success" else "#dc2626" if status == "failed" else "#d97706"
            result_rows += (
                f"<tr>"
                f"<td>{html.escape(str(r.get('restaurant_number', '')))}</td>"
                f"<td>{html.escape(str(r.get('device_id', '')))}</td>"
                f"<td>{html.escape(str(r.get('script_name', '')))}</td>"
                f"<td style='color:{color};font-weight:bold'>{html.escape(status)}</td>"
                f"<td><pre style='margin:0'>{html.escape(str(r.get('result_output', '') or ''))}</pre></td>"
                f"<td><pre style='margin:0;color:#dc2626'>{html.escape(str(r.get('stderr', '') or ''))}</pre></td>"
                f"</tr>"
            )
        script_section = f"""
        <div class=\"section-title\">Proactive Script Results</div>
        <table>
            <tr>
                <th>Restaurant</th>
                <th>Device ID</th>
                <th>Script</th>
                <th>Status</th>
                <th>Output</th>
                <th>Error</th>
            </tr>
            {result_rows}
        </table>
        """

    html_body = html_body_template.format(
        incident_description=html.escape(str(rule["incident_description"])),
        violation_count=len(records),
        cooldown_label=format_cooldown_label(cooldown_hours),
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

            refused = server.sendmail(
                SMTP_SENDER,
                recipients,
                msg.as_string(),
            )

        if refused:
            print(f"[WARN] Some recipients were refused: {refused}")

        print(f"Email sent successfully via Mailjet to {recipients}")
        return True

    except Exception as e:

        print(f"Email send failed: {str(e)}")
        return False

# =============================
# WebSocket Proactive Script
# =============================

def run_proactive_script(restaurant_number, script_name):

    print(f"Triggering script {script_name} for restaurant {restaurant_number}")

    if STAGE_NAME == "prod":
        endpoint = "https://j3v4n25iwa.execute-api.eu-central-1.amazonaws.com/prod/"
    elif STAGE_NAME == "nprod":
        endpoint = "https://egnv9vgjjh.execute-api.eu-central-1.amazonaws.com/nprod/"
    else:
        endpoint = "https://vugx1b0qef.execute-api.eu-central-1.amazonaws.com/dev/"

    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)

    scan_kwargs = {
        "FilterExpression": Attr("restaurant_number").eq(str(restaurant_number))
        & Attr("status").eq("connected")
    }

    items = []
    response = connections_table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))

    while response.get("LastEvaluatedKey"):
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        response = connections_table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

    triggered = []

    for item in items:

        command_id = str(uuid.uuid4())
        message = {
            "command_id": command_id,
            "script_name": script_name,
            "action": "trigger_script",
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
        }

        try:

            apigw.post_to_connection(
                ConnectionId=item["connectionId"],
                Data=json.dumps(message).encode(),
            )

            triggered.append({
                "command_id": command_id,
                "restaurant_number": str(restaurant_number),
                "script_name": script_name,
            })

            print(f"Script triggered: command_id={command_id} connection={item['connectionId']}")

        except ClientError as e:
            print(f"[WARN] Failed to send to connection {item['connectionId']}: {e}")

    return triggered


def poll_script_results(triggered_commands, timeout_seconds=30):

    if not results_table:
        print("[WARN] RESULTS_TABLE_NAME not configured — skipping result polling")
        return []

    remaining = {t["command_id"]: t for t in triggered_commands}
    collected = []
    deadline = time.time() + timeout_seconds

    while remaining and time.time() < deadline:

        for command_id in list(remaining.keys()):
            try:
                resp = results_table.get_item(Key={"result_id": command_id})
                item = resp.get("Item")
                if item:
                    collected.append(item)
                    del remaining[command_id]
            except Exception as e:
                print(f"[WARN] Error polling result for {command_id}: {e}")

        if remaining:
            time.sleep(3)

    # Commands that never responded within the timeout
    for command_id, triggered in remaining.items():
        print(f"[WARN] Timeout waiting for result: command_id={command_id}")
        collected.append({
            "result_id": command_id,
            "restaurant_number": triggered["restaurant_number"],
            "script_name": triggered["script_name"],
            "execution_status": "timeout",
            "result_output": "",
            "stderr": "No response received within timeout period.",
        })

    return collected