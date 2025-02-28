import boto3
import os
import logging

# Athena settings
athena_client = boto3.client('athena')
database = os.environ['ATHENA_DATABASE']
output_location = os.environ['ATHENA_OUTPUT_LOCATION']
folder_name = 'athena_views/'  # Local folder path within Lambda

# Configure logging
logger = logging.getLogger()
logger.setLevel("INFO")


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

        # Wait for the query to complete
        athena_client.get_query_execution(QueryExecutionId=query_execution_id)

        # Fetch the results
        result = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        views = [row['Data'][0]['VarCharValue'] for row in result['ResultSet']['Rows'][1:]]  # Skip header row
    except Exception as e:
        # Log the error and continue
        logger.error(f"An error occurred while running Athena query {query}: {str(e)}")
        raise
    return views


def lambda_handler(event, context):
    try:
        # Get the list of existing views
        existing_views = get_existing_views()
        logger.info(f"Views '{existing_views}'")
        # List all files in the specified local folder
        files = [f for f in os.listdir(folder_name) if f.endswith('.sql')]

        for file_name in files:
            view_name = file_name.split('.')[0]  # Assuming view name is the same as file name without extension
            logger.info(f"Views '{view_name}'")
            if view_name not in existing_views:
                file_path = os.path.join(folder_name, file_name)
                # Read the SQL query from each file
                with open(file_path, 'r') as file:
                    query = file.read()

                # Execute the SQL query in Athena
                athena_client.start_query_execution(
                    QueryString=query,
                    QueryExecutionContext={'Database': database},
                    ResultConfiguration={'OutputLocation': output_location}
                )

        return {
            'statusCode': 200,
            'body': 'All queries executed successfully!'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Error: {str(e)}"
        }
