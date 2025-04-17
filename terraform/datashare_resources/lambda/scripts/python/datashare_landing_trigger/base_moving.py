import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

def base_moving(src_bucket, key, target_bucket, destination_path):
    file_name = key.split("/")[-1]
    dest_key = f"{destination_path}/{file_name}"
    s3.copy_object(
        Bucket=target_bucket,
        CopySource={"Bucket": src_bucket, "Key": key},
        Key=dest_key,
    )
    logger.info(f"Copied to: s3://{target_bucket}/{dest_key}")
