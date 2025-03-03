import time
import boto3
import os
import logging

# Athena settings
database = os.environ['ATHENA_DATABASE']
athena_output_location = os.environ['ATHENA_OUTPUT_LOCATION']
output_location = f"s3://{athena_output_location}"
folder_name = 'athena_views/'  # Local folder path within Lambda
athena_client = boto3.client('athena', region_name='eu-central-1')

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


def get_existing_views():
    query = "SHOW VIEWS"
    try:
        logger.info(f"Starting the Athena query to check view exists in '{database}'")
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            ResultConfiguration={'OutputLocation': output_location}
        )
        query_execution_id = response['QueryExecutionId']
        if not check_query_status(query_execution_id):
            raise Exception("Query failed or was cancelled")
        # Fetch the results
        result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        views = [row['Data'][0]['VarCharValue'] for row in result['ResultSet']['Rows']]
    except Exception as e:
        # Log the error and continue
        logger.error(f"An error occurred while running Athena query {query}: {str(e)}")
        raise
    return views


def lambda_handler(event, context):
    errors = []
    try:
        # Get the list of existing views
        existing_views = get_existing_views()
        logger.info(f"Views that are already created '{existing_views}'")
        # List all files in the specified local folder
        files = [f for f in os.listdir(folder_name) if f.endswith('.sql')]

        for file_name in files:
            view_name = file_name.split('.')[0]
            if view_name not in existing_views:
                logger.info(f"Creating athena '{view_name}'")
                file_path = os.path.join(folder_name, file_name)
                # Read the SQL query from each file
                with open(file_path, 'r') as file:
                    query = file.read()

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
