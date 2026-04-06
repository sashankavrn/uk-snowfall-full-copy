import boto3
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
EMAIL_TO = "venkata.adapa@uk.mcd.com"

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

    rules = rules_table.scan()["Items"]

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

    results = athena.get_query_results(QueryExecutionId=execution_id)

    rows = results["ResultSet"]["Rows"]

    records = []

    for row in rows[1:]:

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

    return records

# =============================
# Rule Processing
# =============================

def process_rule(rule, records):

    # Only valid restaurant values
    restaurants = [r["restaurant_number"] for r in records if r["restaurant_number"]]

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

    # STEP 3 Create Ticket
    create_ticket(rule, records)

    # STEP 4 Send Email
    if rule.get("email_alert"):

        send_email(rule, records, script_output)

# =============================
# Cooldown Logic
# =============================

def should_send_alert(rule, restaurants):

    cooldown_hours = int(rule.get("cool_down_period", 0))

    response = tickets_table.scan(
        FilterExpression=Attr("rule_id").eq(rule["rule_id"]) & Attr("status").eq("OPEN")
    )

    items = response.get("Items", [])

    if not items:
        return True

    last_ticket = items[0]

    last_restaurants = set(last_ticket.get("violating_restaurants", []))
    current_restaurants = set(restaurants)

    last_time_str = last_ticket.get("last_alert_time")

    last_time = datetime.fromisoformat(last_time_str) if last_time_str else None
    now = datetime.now(ZoneInfo("Europe/London"))

    # If no restaurant rules → always allow based on cooldown only
    if not restaurants:
        if last_time and cooldown_hours > 0:
            elapsed = (now - last_time).total_seconds() / 3600
            return elapsed >= cooldown_hours
        return True

    if not current_restaurants.issubset(last_restaurants):
        print("New restaurant detected")
        return True

    if last_time and cooldown_hours > 0:

        elapsed = (now - last_time).total_seconds() / 3600

        if elapsed >= cooldown_hours:
            print("Cooldown expired")
            return True

    return False

# =============================
# Create Ticket
# =============================

def create_ticket(rule, records):

    restaurants = [r["restaurant_number"] for r in records if r["restaurant_number"]]

    first_record = records[0]

    ticket_id = f"INC{int(time.time())}"

    timestamp = datetime.now(ZoneInfo("Europe/London")).isoformat()

    item = {
        "ticket_id": ticket_id,
        "rule_id": rule["rule_id"],
        "restaurant_number": first_record.get("restaurant_number"),
        "message": first_record["message"],
        "status": "OPEN",
        "created_at": timestamp,
        "violating_restaurants": restaurants,
        "last_alert_time": timestamp
    }

    tickets_table.put_item(Item=item)

    print(f"Ticket created: {ticket_id}")

# =============================
# Email (SMTP - Mailjet)
# =============================

def send_email(rule, records, script_output):

    subject = f"{rule['incident_description']} - [{len(records)} Alerts]"

    has_restaurant = any(r.get("restaurant_number") for r in records)

    html = """
    <html><body>
    <h3>Proactive Alert</h3>
    <table border="1" cellpadding="6">
    <tr>
    <th>S.No</th>
    """

    if has_restaurant:
        html += "<th>Restaurant</th>"

    html += "<th>Message</th></tr>"

    for i, r in enumerate(records, start=1):

        html += "<tr>"
        html += f"<td>{i}</td>"

        if has_restaurant:
            html += f"<td>{r.get('restaurant_number','')}</td>"

        html += f"<td>{r['message']}</td>"
        html += "</tr>"

    html += "</table>"

    if script_output:

        html += f"""
        <h4>Proactive Script Output</h4>
        <pre>{json.dumps(script_output, indent=2)}</pre>
        """

    html += "</body></html>"

    try:

        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject
        msg["From"] = SMTP_SENDER
        msg["To"] = EMAIL_TO

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(SMTP_USERNAME, SMTP_PASSWORD)

            server.sendmail(
                SMTP_SENDER,
                EMAIL_TO.split(","),
                msg.as_string(),
            )

        print("Email sent successfully via Mailjet")

    except Exception as e:

        print(f"Email send failed: {str(e)}")

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