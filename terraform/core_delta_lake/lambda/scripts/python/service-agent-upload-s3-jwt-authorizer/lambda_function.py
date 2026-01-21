import json
import jwt
import boto3
import os
import csv
from io import StringIO

# AWS clients
s3 = boto3.client("s3")
secretsmanager = boto3.client("secretsmanager")

# Environment variables
# BUCKET = os.environ.get("BUCKET_NAME", "staging")
# SERVER_LIST_KEY = "serverlist/List of Restaurant Servers.csv"
# SECRET_NAME = os.environ.get("SECRET_NAME", "UK_SNOWFALL")
# SECRET_KEY = os.environ.get("SECRET_KEY", "JWT_SECRET")
JWT_ALGORITHM = "HS256"
BUCKET = os.environ.get('TARGET_BUCKET')  # Updated here
SERVER_LIST_KEY = 'server_list/List of Restaurant Servers.csv'
SECRET_NAME = 'uk-snowfall-service-agent'
SECRET_KEY = 'uk-snowfall-service-agent-key'


def get_jwt_secret():
    """
    Fetch JWT secret from Secrets Manager
    """
    response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
    secret_dict = json.loads(response["SecretString"])
    return secret_dict[SECRET_KEY]


def load_allowed_machines_from_s3():
    """
    Load allowed machine names from S3 CSV
    """
    response = s3.get_object(Bucket=BUCKET, Key=SERVER_LIST_KEY)
    csv_data = response["Body"].read().decode("utf-8")
    csv_reader = csv.DictReader(StringIO(csv_data))

    return {
        row["server_name"].strip()
        for row in csv_reader
        if row.get("server_name") and row["server_name"].strip()
    }

def generate_policy(principal_id, effect, resource, context):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        },
        "context": context
    }


def lambda_handler(event, context):
    print(event)
    try:
        print("inside try")
        
        # -----------------------------
        # 1. Read Authorization header
        # -----------------------------
        auth_header = event.get("authorizationToken", "")

        if not auth_header.startswith("Bearer "):
            return {"isAuthorized": False}

        token = auth_header.replace("Bearer ", "").strip()
        print(token)

        # -----------------------------
        # 2. Decode JWT using secret
        # -----------------------------
        jwt_secret = get_jwt_secret()

        decoded = jwt.decode(
            token,
            jwt_secret,
            algorithms=[JWT_ALGORITHM]
        )

        print(decoded)

        # -----------------------------
        # 3. Validate required claims
        # -----------------------------
        machine = decoded.get("machine")

        if not machine:
            print("Missing required JWT claims")
            return {"isAuthorized": False}

        # -----------------------------
        # 4. Validate machine against S3
        # -----------------------------
        allowed_machines = load_allowed_machines_from_s3()

        if machine not in allowed_machines:
            print(f"Machine '{machine}' not in allowed list")
            return {"isAuthorized": False}

        # -----------------------------
        # 5. PASS CONTEXT TO NEXT LAMBDA
        # -----------------------------
        print("machine: ",machine)
        auth_context = {
            "machine": str(machine)
        }
        return generate_policy(
            principal_id=machine,
            effect="Allow",
            resource=event["methodArn"],
            context=auth_context
        )

    except jwt.ExpiredSignatureError:
        print("JWT expired")
        return {"isAuthorized": False}

    except jwt.InvalidTokenError as e:
        print("Invalid JWT:", str(e))
        return {"isAuthorized": False}

    except Exception as e:
        print("Authorizer error:", str(e))
        return {"isAuthorized": False}