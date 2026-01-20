import boto3
import base64
import os
import jwt
import json
import csv
from io import StringIO
from datetime import datetime
from pathlib import Path
import re

s3 = boto3.client('s3')
secretsmanager = boto3.client('secretsmanager')

# Environment Variables
BUCKET = os.environ.get('TARGET_BUCKET')  # Updated here
SERVER_LIST_KEY = 'server_list/List of Restaurant Servers.csv'
SECRET_NAME = 'uk-snowfall-service-agent'
SECRET_KEY = 'uk-snowfall-service-agent-key'

ALLOWED_EXTENSIONS = ('.xml', '.csv')
ALLOWED_CONTENT_TYPES = ('text/xml', 'application/xml', 'text/csv', 'application/csv')

def get_jwt_secret():
    try:
        response = secretsmanager.get_secret_value(SecretId=SECRET_NAME)
        secret_dict = json.loads(response['SecretString'])
        return secret_dict[SECRET_KEY]
    except Exception as e:
        raise Exception(f"Error retrieving JWT secret: {str(e)}")

def load_allowed_machines_from_s3():
    try:
        response = s3.get_object(Bucket=BUCKET, Key=SERVER_LIST_KEY)
        csv_data = response['Body'].read().decode('utf-8')
        csv_reader = csv.DictReader(StringIO(csv_data))
        server_names = {row['server_name'].strip() for row in csv_reader if 'server_name' in row and row['server_name'].strip()}
        return server_names
    except Exception as e:
        raise Exception(f"Failed to load allowed machines from S3: {str(e)}")

def extract_filename(content_disposition):
    if "filename=" in content_disposition:
        parts = content_disposition.split("filename=")
        filename = parts[1].strip().strip('"').strip("'")
        return filename
    return None

def lambda_handler(event, context):
    try:
        headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
        auth_header = headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "body": "Unauthorized: Missing or invalid Authorization header"
            }

        token = auth_header.split("Bearer ")[1].strip()
        JWT_SECRET = get_jwt_secret()

        try:
            decoded_payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return {"statusCode": 401, "body": "Unauthorized: Token has expired"}
        except jwt.InvalidTokenError as e:
            return {"statusCode": 401, "body": f"Unauthorized: Invalid token - {str(e)}"}

        machine_name = decoded_payload.get("machine")
        if not machine_name:
            return {"statusCode": 403, "body": "Forbidden: JWT token missing 'machine' field"}

        ALLOWED_MACHINES = load_allowed_machines_from_s3()
        if machine_name not in ALLOWED_MACHINES:
            return {
                "statusCode": 403,
                "body": f"Forbidden: Machine '{machine_name}' is not authorized"
            }

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

        body = event['body']
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body)
        else:
            body = body.encode('utf-8')

        # Parse filename and derive folder name
        file_stem = Path(filename).stem  # Removes the extension
        # Step 1: Remove patterns like `_123_`, `_123`, `123_`, or just `123`
        step1 = re.sub(r'(_)?\d+(_)?', lambda m: '_' if m.group(1) and m.group(2) else '', file_stem)

        # Step 2: Remove leading special characters (non-alphabetic)
        folder_name = re.sub(r'^[^a-zA-Z]+', '', step1)

        # Step 3: Replace dots with _
        folder_name = folder_name.replace('.', '_')

         # Step 4: Replace - with _
        folder_name = folder_name.replace('-', '_')

        # folder_name = re.sub(r'[^a-zA-Z0-9_]', '_', file_stem)  # Replace non-alphanumeric chars with "_"

        # Construct the S3 key with the folder inside machine_name
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        s3_key = f"uploads/{folder_name}/{machine_name}/{timestamp}_{filename}"

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


# import boto3
# import base64
# import os
# import json
# import re
# from datetime import datetime
# from pathlib import Path

# s3 = boto3.client("s3")

# # Environment Variables
# BUCKET = os.environ.get("TARGET_BUCKET")
# ALLOWED_EXTENSIONS = (".xml", ".csv")
# ALLOWED_CONTENT_TYPES = ("text/xml", "application/xml", "text/csv", "application/csv")


# def extract_filename(content_disposition):
#     """
#     Extract filename from Content-Disposition header.
#     """
#     if not content_disposition:
#         return None

#     if "filename=" in content_disposition:
#         filename = content_disposition.split("filename=")[1].strip().strip('"').strip("'")
#         return filename

#     return None


# def clean_folder_name(filename_stem):
#     """
#     Clean folder name using your rules:
#     - Remove numeric patterns like _123_, _123, 123_, or 123
#     - Remove leading non-alphabetic characters
#     - Replace dots and hyphens with underscores
#     """
#     # Step 1: Remove numeric patterns
#     step1 = re.sub(r"(_)?\d+(_)?", lambda m: "_" if m.group(1) and m.group(2) else "", filename_stem)

#     # Step 2: Remove leading non-alphabetic characters
#     cleaned = re.sub(r"^[^a-zA-Z]+", "", step1)

#     # Step 3: Replace dots and hyphens
#     cleaned = cleaned.replace(".", "_").replace("-", "_")

#     return cleaned


# def lambda_handler(event, context):
#     try:
#         # ----------------------------------------------------
#         # 1. Extract context passed from the Custom Authorizer
#         # ----------------------------------------------------
#         auth_ctx = event.get("requestContext", {}).get("authorizer", {})
#         machine_name = auth_ctx.get("machine")
#         restaurant_number = auth_ctx.get("restaurant_number")
#         device_id = auth_ctx.get("device_id")

#         if not machine_name:
#             return {"statusCode": 400, "body": "Missing machine context from authorizer"}

#         # ----------------------------------------------------
#         # 2. Extract headers
#         # ----------------------------------------------------
#         headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
#         content_disposition = headers.get("content-disposition", "")
#         content_type = headers.get("content-type", "").lower()

#         # ----------------------------------------------------
#         # 3. Validate filename
#         # ----------------------------------------------------
#         filename = extract_filename(content_disposition)
#         if not filename:
#             return {
#                 "statusCode": 400,
#                 "body": "Missing filename. Include Content-Disposition header with filename="
#             }

#         if not filename.lower().endswith(ALLOWED_EXTENSIONS):
#             return {
#                 "statusCode": 400,
#                 "body": "Invalid file type. Only .xml and .csv files are allowed."
#             }

#         # ----------------------------------------------------
#         # 4. Validate content-type
#         # ----------------------------------------------------
#         if content_type not in ALLOWED_CONTENT_TYPES:
#             return {
#                 "statusCode": 400,
#                 "body": f"Invalid content-type '{content_type}'. Only XML and CSV types are allowed."
#             }

#         # ----------------------------------------------------
#         # 5. Decode body
#         # ----------------------------------------------------
#         body = event.get("body", "")
#         if event.get("isBase64Encoded", False):
#             body = base64.b64decode(body)
#         else:
#             body = body.encode("utf-8")

#         # ----------------------------------------------------
#         # 6. Clean folder name
#         # ----------------------------------------------------
#         file_stem = Path(filename).stem
#         folder_name = clean_folder_name(file_stem)

#         # ----------------------------------------------------
#         # 7. Build S3 key
#         # ----------------------------------------------------
#         timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
#         s3_key = f"uploads/{folder_name}/{machine_name}/{timestamp}_{filename}"

#         # ----------------------------------------------------
#         # 8. Upload to S3
#         # ----------------------------------------------------
#         s3.put_object(
#             Bucket=BUCKET,
#             Key=s3_key,
#             Body=body,
#             ContentType=content_type
#         )

#         # ----------------------------------------------------
#         # 9. Success response
#         # ----------------------------------------------------
#         return {
#             "statusCode": 200,
#             "body": json.dumps({
#                 "message": "File uploaded successfully",
#                 "filename": filename,
#                 "machine": machine_name,
#                 "restaurant_number": restaurant_number,
#                 "device_id": device_id,
#                 "s3_key": s3_key
#             })
#         }

#     except Exception as e:
#         return {
#             "statusCode": 500,
#             "body": f"Internal server error: {str(e)}"
#         }
