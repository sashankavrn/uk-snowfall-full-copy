import boto3
import os
import logging
import time

# Environment variables
database = os.environ['ATHENA_DATABASE']
bucket_name = os.environ['S3_BUCKET_NAME']
workgroup_name = os.environ['WORKGROUP_NAME']

# Clients
athena_client = boto3.client('athena', region_name='eu-central-1')
s3_client = boto3.client('s3')

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
temp_prefix = 'server_list/temp_results/'
destination_key = 'server_list/List of Restaurant Servers.csv'
output_location = f's3://{bucket_name}/{temp_prefix}'


def check_query_status(execution_id):
    start_time = time.time()
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            return True
        elif status in ['FAILED', 'CANCELLED']:
            return False
        elif time.time() - start_time > 50:
            raise TimeoutError("Query execution timed out")
        time.sleep(1)


def copy_athena_result_file(bucket, prefix, query_execution_id, destination_key):
    """
    Copies the Athena result file from the temporary location to a fixed destination key.
    """
    result_prefix = f"{prefix}{query_execution_id}"
    result_objects = s3_client.list_objects_v2(
        Bucket=bucket,
        Prefix=result_prefix
    )

    if 'Contents' not in result_objects or len(result_objects['Contents']) == 0:
        raise Exception("No result file found in S3 after Athena query execution.")

    # Find the CSV file
    result_file_key = next(
        (obj['Key'] for obj in result_objects['Contents'] if obj['Key'].endswith('.csv')),
        None
    )

    if not result_file_key:
        raise Exception("CSV result file not found in Athena output.")

    # Copy to final destination
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': result_file_key},
        Key=destination_key
    )

    # Delete all files in the temp folder
    temp_objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if 'Contents' in temp_objects:
        for obj in temp_objects['Contents']:
            s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
            logger.info(f"Deleted temp file: {obj['Key']}")

    logger.info(f"Copied result file to s3://{bucket}/{destination_key}")

def lambda_handler(event, context):
    try:
        query = """
            SELECT DISTINCT
                "store_number",
                "server_number",
                "server_name"
            FROM (
                (SELECT DISTINCT
                --get GSC01 names
                    "store_number",
                    1 "server_number",
                    case when store_number < 7000 
                        then concat('UK', format('%05d', "store_number"), 'GSC01')
                        else concat('IE', format('%05d', "store_number"), 'GSC01')
                    end "server_name"
                FROM 
                    "uk_snowfall_processed"."ods_location_hierarchy"
                )
                UNION ALL
                (SELECT DISTINCT
                --get GSC02 names
                    "store_number",
                    2 "server_number",
                    case when store_number < 7000 
                        then concat('UK', format('%05d', "store_number"), 'GSC02')
                        else concat('IE', format('%05d', "store_number"), 'GSC02')
                    end "server_name"
                FROM 
                    "uk_snowfall_processed"."ods_location_hierarchy"
                )
                UNION ALL
                (SELECT DISTINCT
                --catch any additional servers from New Relic data (including labs)
                    "restaurant_number" "store_number",
                    CAST(regexp_extract("device", '[0-9]+') AS INTEGER) "server_number",
                    "host_name" "server_name"
                FROM 
                    "uk_snowfall_processed"."newrelic_rmp_device_info"
                WHERE 
                    "device" like 'GSC%'
                )
            )
        """

        logger.info("Starting Athena query execution...")
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location},
            WorkGroup=workgroup_name
        )

        query_execution_id = response['QueryExecutionId']
        if not check_query_status(query_execution_id):
            raise Exception("Athena query failed or was cancelled")


        # Copy result file to final destination
        copy_athena_result_file(
            bucket=bucket_name,
            prefix=temp_prefix,
            query_execution_id=query_execution_id,
            destination_key=destination_key
        )

        return {
            'statusCode': 200,
            'body': f"Result available at: s3://{bucket_name}/{destination_key}"
        }

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
