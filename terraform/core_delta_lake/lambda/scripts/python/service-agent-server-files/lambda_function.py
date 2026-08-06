import boto3
import os
import logging
from datetime import datetime, timezone

s3 = boto3.client('s3')
sns = boto3.client('sns')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SOURCE_BUCKET = os.environ.get('SOURCE_BUCKET')
TARGET_BUCKET = os.environ.get('TARGET_BUCKET')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')


def send_sns_notification(subject, message):
    try:
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
        logger.info(f"SNS notification sent: {response['MessageId']}")
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")


def copy_key(source_key, function_name):
    if source_key.endswith("/"):
        return  # skip folder placeholders

    if source_key.startswith("uploads/"):
        relative_key = source_key[len("uploads/"):]
    else:
        relative_key = source_key

    if not relative_key:
        return  # skip the uploads/ folder object itself

    target_key = f"service_agent_server_files/uploads/{relative_key}"
    logger.info(f"Copying s3://{SOURCE_BUCKET}/{source_key} -> s3://{TARGET_BUCKET}/{target_key}")

    try:
        s3.copy_object(
            Bucket=TARGET_BUCKET,
            CopySource={'Bucket': SOURCE_BUCKET, 'Key': source_key},
            Key=target_key
        )
        logger.info(f"Successfully copied to s3://{TARGET_BUCKET}/{target_key}")
    except Exception as e:
        error_msg = f"Failed to copy {source_key} to {TARGET_BUCKET}/{target_key}: {str(e)}"
        logger.error(error_msg)
        send_sns_notification(
            subject=f"Lambda Copy Failure - {function_name}",
            message=error_msg
        )


def list_keys(bucket, prefix):
    """Return a set of all keys under prefix in bucket (skips folder placeholders)."""
    paginator = s3.get_paginator('list_objects_v2')
    keys = set()
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('/'):
                keys.add(key)
    return keys


def run_verify(prefix, copy_missing, function_name, context):
    """
    Compares source uploads/ against target service_agent_server_files/uploads/.
    If copy_missing=True, copies any missing files (with timeout guard).
    Invoke: {"verify": true, "prefix": "uploads/bios_info/", "copy_missing": true}
    """
    logger.info(f"Verify mode: prefix={prefix} copy_missing={copy_missing}")

    source_keys = list_keys(SOURCE_BUCKET, prefix)
    logger.info(f"Source objects found: {len(source_keys)}")

    # Build expected target keys
    missing = []
    for sk in source_keys:
        relative = sk[len("uploads/"):] if sk.startswith("uploads/") else sk
        if not relative:
            continue
        expected_target = f"service_agent_server_files/uploads/{relative}"
        missing.append((sk, expected_target))

    # Get existing target keys — scoped to the same sub-folder as the source prefix
    target_prefix = (f"service_agent_server_files/uploads/{prefix[len('uploads/'):]}"
                     if prefix.startswith("uploads/")
                     else "service_agent_server_files/uploads/")
    target_keys = list_keys(TARGET_BUCKET, target_prefix)
    logger.info(f"Target objects found: {len(target_keys)}")

    missing_files = [(sk, tk) for sk, tk in missing if tk not in target_keys]
    logger.info(f"Missing files: {len(missing_files)}")

    for sk, tk in missing_files[:50]:  # log first 50 to avoid log flood
        logger.info(f"  MISSING: {sk} -> {tk}")

    if not copy_missing:
        summary = (f"Verify complete (dry-run). Source: {len(source_keys)}, "
                   f"Target: {len(target_keys)}, Missing: {len(missing_files)}")
        logger.info(summary)
        send_sns_notification(subject=f"Verify Result - {function_name}", message=summary)
        return {'status': 'verify_complete', 'source_count': len(source_keys),
                'target_count': len(target_keys), 'missing_count': len(missing_files)}

    # Copy missing files with timeout guard
    copied = 0
    last_key = None
    for sk, tk in missing_files:
        if context.get_remaining_time_in_millis() < 60_000:
            msg = (f"Verify+copy paused at timeout. Copied {copied}/{len(missing_files)} missing files. "
                   f"Last source key: {last_key}")
            logger.warning(msg)
            send_sns_notification(subject=f"Verify+Copy Paused - {function_name}", message=msg)
            return {'status': 'paused', 'copied_missing': copied,
                    'total_missing': len(missing_files), 'last_key': last_key}
        copy_key(sk, function_name)
        copied += 1
        last_key = sk

    summary = (f"Verify+copy complete. Source: {len(source_keys)}, "
               f"Target: {len(target_keys)}, Missing copied: {copied}")
    logger.info(summary)
    send_sns_notification(subject=f"Verify+Copy Complete - {function_name}", message=summary)
    return {'status': 'verify_complete', 'source_count': len(source_keys),
            'target_count': len(target_keys), 'missing_copied': copied}


def run_backfill(start_date_str, start_after, prefix, function_name, context):
    """
    Lists all objects under prefix in SOURCE_BUCKET and copies them to TARGET_BUCKET.
    start_date_str : ISO date string e.g. '2026-04-30'
    start_after    : S3 key to resume from (pass 'resume_from_key' from a previous run)
    prefix         : S3 prefix e.g. 'uploads/bios_info/' (default 'uploads/')
    """
    start_date = None
    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str).replace(tzinfo=timezone.utc)
        logger.info(f"Backfill start_date filter: {start_date}")

    logger.info(f"Backfill prefix: {prefix}")
    if start_after:
        logger.info(f"Resuming after key: {start_after}")

    paginator = s3.get_paginator('list_objects_v2')
    paginate_kwargs = {'Bucket': SOURCE_BUCKET, 'Prefix': prefix}
    if start_after:
        paginate_kwargs['StartAfter'] = start_after

    pages = paginator.paginate(**paginate_kwargs)
    total = 0
    copied = 0
    skipped = 0
    last_key = start_after

    for page in pages:
        for obj in page.get('Contents', []):
            if context.get_remaining_time_in_millis() < 60_000:
                msg = (f"Approaching timeout — pausing. Copied: {copied}, Skipped: {skipped}. "
                       f"Resume with start_after: {last_key}")
                logger.warning(msg)
                send_sns_notification(subject=f"Backfill Paused - {function_name}", message=msg)
                return {'status': 'paused', 'copied': copied, 'skipped': skipped,
                        'resume_from_key': last_key, 'detail': msg}

            total += 1
            source_key = obj['Key']
            last_modified = obj['LastModified']

            if start_date and last_modified < start_date:
                skipped += 1
                last_key = source_key
                continue

            copy_key(source_key, function_name)
            copied += 1
            last_key = source_key

    summary = (f"Backfill complete. Total: {total}, Copied: {copied}, Skipped: {skipped}")
    logger.info(summary)
    send_sns_notification(subject=f"Backfill Complete - {function_name}", message=summary)
    return {'status': 'backfill_complete', 'copied': copied, 'skipped': skipped, 'detail': summary}


def lambda_handler(event, context):
    # ── Verify mode ────────────────────────────────────────────────────────────
    # Dry-run:        {"verify": true, "prefix": "uploads/bios_info/"}
    # Fix missing:    {"verify": true, "prefix": "uploads/bios_info/", "copy_missing": true}
    # All folders:    {"verify": true, "prefix": "uploads/"}
    if event.get('verify'):
        prefix       = event.get('prefix', 'uploads/')
        copy_missing = event.get('copy_missing', False)
        return run_verify(prefix, copy_missing, context.function_name, context)

    # ── Backfill mode ──────────────────────────────────────────────────────────
    # First run:  {"backfill": true, "start_date": "2026-04-30", "prefix": "uploads/bios_info/"}
    # Resume:     {"backfill": true, "start_date": "2026-04-30", "prefix": "uploads/bios_info/", "start_after": "<key>"}
    if event.get('backfill'):
        start_date_str = event.get('start_date', '2026-04-30')
        start_after    = event.get('start_after', '')
        prefix         = event.get('prefix', 'uploads/')
        return run_backfill(start_date_str, start_after, prefix, context.function_name, context)

    # ── Normal S3-trigger mode ─────────────────────────────────────────────────
    if 'Records' not in event:
        logger.warning(f"No 'Records' key in event. Event was: {event}")
        return

    for record in event['Records']:
        source_bucket = record['s3']['bucket']['name']
        source_key = record['s3']['object']['key']

        if source_bucket != SOURCE_BUCKET:
            logger.warning(f"Ignoring event from unexpected bucket: {source_bucket}")
            continue

        copy_key(source_key, context.function_name)