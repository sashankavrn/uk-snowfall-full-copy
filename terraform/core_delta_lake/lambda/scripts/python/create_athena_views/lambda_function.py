import boto3
import os
import logging
import time

# Athena settings
database = os.environ['ATHENA_DATABASE']
athena_output_location = os.environ['ATHENA_OUTPUT_LOCATION']
output_location = f"s3://{athena_output_location}"
bucket_name = os.environ['S3_BUCKET_NAME']
athena_client = boto3.client('athena', region_name='eu-central-1')
s3_client = boto3.client('s3')

# Configure logging
logger = logging.getLogger()
logger.setLevel("INFO")


def check_query_status(execution_id):
    if execution_id is None:
        logger.info('No Athena query execution ID passed in. Exiting the function.')
        return False

    start_time = time.time()

    while True:
        response = athena_client.get_query_execution(QueryExecutionId=execution_id)
        status = response['QueryExecution']['Status']['State']

        if status == 'SUCCEEDED':
            return True
        elif status in ['FAILED', 'CANCELLED']:
            return False
        if time.time() - start_time > 50:
            raise TimeoutError("Query execution timed out")
        time.sleep(1)


def lambda_handler(event, context):
    errors = []
    try:
        for record in event['Records']:
            file_key = record['s3']['object']['key']
            view_name = file_key.split('/')[-1].split('.')[0]
            logger.info(f"Creating athena '{view_name}'")
            # Read the SQL query from each file in S3
            obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
            query = obj['Body'].read().decode('utf-8')

            try:
                # Execute the SQL query in Athena
                response = athena_client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': database},
                    ResultConfiguration={'OutputLocation': output_location}
                )
                query_execution_id = response['QueryExecutionId']
                # Wait for the query to complete
                if not check_query_status(query_execution_id):
                    raise Exception(f"Query for view {view_name} failed or was cancelled")
                logger.info(f"View '{view_name}' created successfully")
            except Exception as e:
                logger.error(f"Failed to create view {view_name}: {str(e)}")
                errors.append(f"Failed to create view {view_name}: {str(e)}")

        if errors:
            raise Exception("Some views failed to be created:\n" + "\n".join(errors))

        return {
            'statusCode': 200,
            'body': 'All queries executed successfully!'
        }
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }