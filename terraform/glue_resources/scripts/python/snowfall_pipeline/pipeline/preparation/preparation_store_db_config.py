from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.data_quality_rules import dq_rules
from delta.tables import DeltaTable
import xml.etree.ElementTree as ET
from pyspark.sql import functions as F
import boto3

class PreparationStoreDbConfig(TransformBase):

    def __init__(self, spark, sc, glueContext, dataset=None, sub_dataset=None, extension=None):
        super().__init__(spark, sc, glueContext, dataset, 'preparation')
        self.spark.conf.set("spark.sql.shuffle.partitions", "1") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.spark.conf.set('spark.sql.caseSensitive', True)
        self.extension = extension
        self.sub_dataset = sub_dataset

        # self.pipeline_config = self.full_configs[self.datasets]
        # self.dq_rule = dq_rules.get(self.datasets)
        self.file_path = f"service_agent_server_files/uploads/{sub_dataset}"
        #self.list_of_files = self.aws_instance.get_files_in_s3_path(f"{self.raw_bucket_name}/{self.file_path}")

    def get_data(self):

        if self.extension == 'xml':
            root_tag = self.extract_root_tag(self.raw_bucket_name, f'{self.file_path}/')
            if root_tag:
                self.logger.info(f'Root tag: {root_tag}')
                df = self.read_data_from_s3(self.raw_bucket_name,self.file_path,'xml', row_tag = root_tag)
        else:
            df = self.read_data_from_s3(self.raw_bucket_name,self.file_path,'csv')

        self.logger.info(f'Columns: {len(df.columns)}')
        self.logger.info(f'Rows: {df.count()}')

        return df

    def transform_data(self, df): 
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Flatten nested DataFrame structure
        2. Drop unnecessary nested field ("_VALUE")
        5. Remove duplicate records
        6. Remove trailing whitespaces
        8. Add CDC (Change Data Capture) columns

        Parameters:
        - df: Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.

        """
        
        df = df.withColumn("agent", F.input_file_name())
        df = df.withColumn("agent", F.regexp_extract(F.col("agent"), rf"{self.sub_dataset}/([^/]+)/", 1))

        if self.extension == 'xml':
            # Step 1: Flatten nested DataFrame structure
            df = self.flatten_nest_df(df)

            # Step 2: Drop unnecessary nested field "_VALUE"
            df = self.drop_nested_field(df, "_VALUE")

        self.logger.info(f'Columns: {len(df.columns)}')
        self.logger.info(f'Rows: {df.count()}')

        # Step 6: Remove trailing whitespaces
        df = self.remove_trailing_whitespace(df)

        # Step 8: Add CDC (Change Data Capture) columns
        df = self.adding_cdc_columns(df)

        return df


    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """
        # Define the S3 save path
        save_output_path = f"s3://{self.preparation_bucket_name}/{self.file_path}/"

        # Check if Delta table needs to be created
        if DeltaTable.isDeltaTable(self.spark,save_output_path) is False:
            self.athena_trigger = True
            
        # Determine whether to create or merge to the Delta table
        if self.athena_trigger:

            # Create the Delta table
            df.write.format("delta").mode("overwrite") \
            .save(save_output_path)
            
        else:

            # Append the Delta table
            df.write.format("delta").mode("append") \
            .save(save_output_path)
            
            # Vacuum the table
            self.vacuum_table(save_output_path,48)

        if not self.aws_instance.athena_table_exists('preparation', self.sub_dataset):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('preparation', self.sub_dataset, save_output_path, self.athena_output_path)
        
        # Move files to the Archive folder
        # for file_name in self.list_of_files:
        #     self.aws_instance.move_s3_object(self.raw_bucket_name, file_name, f"archive/{file_name}")
        
        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed DQ rules"
            self.aws_instance.send_sns_message(message)
        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')



    def extract_root_tag(self, bucket_name, prefix):
        """
        Extract the root tag from the first XML file found in any subfolder under the given prefix.
        Assumes files are XML (no extension check).
        """
        self.logger.info(f"Scanning bucket: {bucket_name}, prefix: {prefix}")

        try:
            # Initialize S3 client
            s3_client = boto3.client('s3')

            # List subfolders under the prefix
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix, Delimiter='/')
            subfolders = [prefix_info['Prefix'].split('/')[-2] for prefix_info in response.get('CommonPrefixes', [])]

            if not subfolders:
                self.logger.warning("No subfolders found.")
                return None

            self.logger.info(f"Found subfolders: {subfolders}")

            root_tag = None

            # Iterate through subfolders until we find a file
            for subfolder in subfolders:
                folder_prefix = f"{prefix}{subfolder}/"
                self.logger.info(f"Checking files in subfolder: {folder_prefix}")

                # List files inside the subfolder
                files_response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
                files = [obj['Key'] for obj in files_response.get('Contents', []) if not obj['Key'].endswith('/')]

                if not files:
                    self.logger.info(f"No files found in {folder_prefix}")
                    continue

                # Take the first file and extract root tag
                first_file_key = files[0]
                self.logger.info(f"Extracting root tag from file: {first_file_key}")

                obj = s3_client.get_object(Bucket=bucket_name, Key=first_file_key)
                xml_content = obj['Body'].read().decode('utf-8')
                root_tag = ET.fromstring(xml_content).tag
                self.logger.info(f"Extracted root tag: {root_tag}")
                return root_tag

            return None

        except Exception as e:
            self.logger.error(f"Error occurred: {str(e)}")
            return None


