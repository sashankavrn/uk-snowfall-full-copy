import boto3
import base64
import os
import jwt  # Requires PyJWT
import json
from datetime import datetime

s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')

# Environment Variables
BUCKET = os.environ.get("TARGET_BUCKET")
SECRET_NAME = 'uk-snowfall-service-agent'  # AWS Secrets Manager name
SECRET_KEY = 'uk-snowfall-service-agent-key'   # Key inside the secret JSON

ALLOWED_MACHINES = set(
    os.environ.get("UK_SERVERS", "").split(",")
)

ALLOWED_EXTENSIONS = ('.xml', '.csv')
ALLOWED_CONTENT_TYPES = ('text/xml', 'application/xml', 'text/csv', 'application/csv')

def get_jwt_secret():
    try:
        response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
        secret_dict = json.loads(response['SecretString'])
        print(secret_dict[SECRET_KEY])
        return secret_dict[SECRET_KEY]
    except Exception as e:
        raise Exception(f"Error retrieving JWT secret: {str(e)}")

def lambda_handler(event, context):
    try:
        # Normalize headers to lowercase
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

        # --- JWT AUTHENTICATION ---
        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "body": "Unauthorized: Missing or invalid Authorization header"
            }

        token = auth_header.split("Bearer ")[1].strip()
        print(token)
        JWT_SECRET = get_jwt_secret()  # Fetch from Secrets Manager

        try:
            decoded_payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return {"statusCode": 401, "body": "Unauthorized: Token has expired"}
        except jwt.InvalidTokenError as e:
            return {"statusCode": 401, "body": f"Unauthorized: Invalid token - {str(e)}"}

        # Ensure 'machine' is in payload
        machine_name = decoded_payload.get("machine")
        if not machine_name:
            return {
                "statusCode": 403,
                "body": "Forbidden: JWT token missing 'machine' field"
            }

        if machine_name not in ALLOWED_MACHINES:
            return {
                "statusCode": 403,
                "body": f"Forbidden: Machine '{machine_name}' is not authorized"
            }

        # --- FILE VALIDATION ---
        content_disposition = headers.get("content-disposition", "")
        filename = extract_filename(content_disposition)

        if not filename:
            return {
                "statusCode": 400,
                "body": "Missing filename. Please include 'Content-Disposition' header with 'filename='."
            }
        if not filename.lower().endswith(ALLOWED_EXTENSIONS):
            return {
                "statusCode": 400,
                "body": "Invalid file type. Only .xml and .csv files are allowed."
            }

        content_type = headers.get("content-type", "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            return {
                "statusCode": 400,
                "body": f"Invalid content-type '{content_type}'. Only XML and CSV types are allowed."
            }

        # Decode file content
        body = event['body']
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body)
        else:
            body = body.encode('utf-8')

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        s3_key = f"uploads/{machine_name}/{timestamp}_{filename}"

        # upload to S3
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=body,
            ContentType=content_type
        )

        return {
            "statusCode": 200,
            "body": f"File '{filename}' uploaded successfully to '{s3_key}'"
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Internal server error: {str(e)}"
        }

def extract_filename(content_disposition):
    if "filename=" in content_disposition:
        parts = content_disposition.split("filename=")
        filename = parts[1].strip().strip('"').strip("'")
        return filename
    return None
