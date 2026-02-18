import boto3
import base64
import os
import json
import re
from datetime import datetime
from pathlib import Path

s3 = boto3.client("s3")

# Environment Variables
BUCKET = os.environ.get("TARGET_BUCKET")
ALLOWED_EXTENSIONS = (".xml", ".csv")
ALLOWED_CONTENT_TYPES = ("text/xml", "application/xml", "text/csv", "application/csv")


def extract_filename(content_disposition):
    """
    Extract filename from Content-Disposition header.
    """
    if not content_disposition:
        return None

    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[1].strip().strip('"').strip("'")
        return filename

    return None


def clean_folder_name(filename_stem):
    """
    Clean folder name using your rules:
    - Remove numeric patterns like _123_, _123, 123_, or 123
    - Remove leading non-alphabetic characters
    - Replace dots and hyphens with underscores
    """
    # Step 1: Remove numeric patterns
    step1 = re.sub(r"(_)?\d+(_)?", lambda m: "_" if m.group(1) and m.group(2) else "", filename_stem)

    # Step 2: Remove leading non-alphabetic characters
    cleaned = re.sub(r"^[^a-zA-Z]+", "", step1)

    # Step 3: Replace dots and hyphens
    cleaned = cleaned.replace(".", "_").replace("-", "_")

    return cleaned


def lambda_handler(event, context):
    try:
        # ----------------------------------------------------
        # 1. Extract context passed from the Custom Authorizer
        # ----------------------------------------------------
        auth_ctx = event.get("requestContext", {}).get("authorizer", {})
        machine_name = auth_ctx.get("machine")
    
        if not machine_name:
            return {"statusCode": 400, "body": "Missing machine context from authorizer"}

        # ----------------------------------------------------
        # 2. Extract headers
        # ----------------------------------------------------
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        content_disposition = headers.get("content-disposition", "")
        content_type = headers.get("content-type", "").lower()

        # ----------------------------------------------------
        # 3. Validate filename
        # ----------------------------------------------------
        filename = extract_filename(content_disposition)
        if not filename:
            return {
                "statusCode": 400,
                "body": "Missing filename. Include Content-Disposition header with filename="
            }

        if not filename.lower().endswith(ALLOWED_EXTENSIONS):
            return {
                "statusCode": 400,
                "body": "Invalid file type. Only .xml and .csv files are allowed."
            }

        # ----------------------------------------------------
        # 4. Validate content-type
        # ----------------------------------------------------
        if content_type not in ALLOWED_CONTENT_TYPES:
            return {
                "statusCode": 400,
                "body": f"Invalid content-type '{content_type}'. Only XML and CSV types are allowed."
            }

        # ----------------------------------------------------
        # 5. Decode body
        # ----------------------------------------------------
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body)
        else:
            body = body.encode("utf-8")

        # ----------------------------------------------------
        # 6. Clean folder name
        # ----------------------------------------------------
        file_stem = Path(filename).stem
        folder_name = clean_folder_name(file_stem)

        # ----------------------------------------------------
        # 7. Build S3 key
        # ----------------------------------------------------
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        s3_key = f"uploads/{folder_name}/{machine_name}/{timestamp}_{filename}"

        # ----------------------------------------------------
        # 8. Upload to S3
        # ----------------------------------------------------
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=body,
            ContentType=content_type
        )

        # ----------------------------------------------------
        # 9. Success response
        # ----------------------------------------------------
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "File uploaded successfully",
                "filename": filename,
                "machine": machine_name,
                "s3_key": s3_key
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Internal server error: {str(e)}"
        }
