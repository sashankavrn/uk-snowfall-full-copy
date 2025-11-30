from snowfall_pipeline.common_utilities.transform_base import TransformBase
import boto3


class ProcessedParentJobTrigger(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)

        self.bucket_name = self.raw_bucket_name
        self.prefix = "service_agent_server_files/uploads/"
        self.main_job_name = "uk-snowfall-main-script-runner"  # Main Glue job name

        self.s3_client = boto3.client('s3')
        self.glue_client = boto3.client('glue')


    def get_data(self):
        """
        List subfolders and trigger the main Glue job with DATASET and EXTENSION.
        """

        self.logger.info(f"Scanning bucket: {self.bucket_name}, prefix: {self.prefix}")

        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.prefix, Delimiter='/')
            subfolders = [prefix_info['Prefix'].split('/')[-2] for prefix_info in response.get('CommonPrefixes', [])]

            if not subfolders:
                self.logger.warning("No subfolders found.")
                return

            self.logger.info(f"Found subfolders: {subfolders}")

            for subfolder in subfolders:
                folder_prefix = f"{self.prefix}{subfolder}/"
                self.logger.info(f"Checking files in subfolder: {folder_prefix}")

                # List files inside the subfolder
                files_response = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=folder_prefix)
                extension = 'unknown'

                for obj in files_response.get('Contents', []):
                    key = obj['Key']
                    filename = key.split('/')[-1]
                    if '.' in filename:  # Ensure it's a file
                        extension = filename.split('.')[-1].lower()
                        break  # Stop after first file 
                    
                self.logger.info(f"Extension for {subfolder}: {extension}")

                #Trigger Glue job with DATASET and EXTENSION
                job_run = self.glue_client.start_job_run(
                    JobName=self.main_job_name,
                    Arguments={
                        '--GROUP': 'preparation',
                        '--DATASET': 'store_db_config',
                        '--SUB_DATASET': subfolder,
                        '--EXTENSION': extension
                    }
                )

                self.logger.info(f"Main job triggered for {subfolder}, JobRunId: {job_run['JobRunId']}")

        except Exception as e:
            self.logger.error(f"Error triggering main job: {str(e)}")
            raise

        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')

