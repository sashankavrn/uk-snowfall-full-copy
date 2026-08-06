from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.data_quality_rules import dq_rules
from delta.tables import DeltaTable
import xml.etree.ElementTree as ET
from pyspark.sql import functions as F, types as T
import boto3

class PreparationServiceAgentWorkerJob(TransformBase):
    def __init__(self, spark, sc, glueContext, dataset=None, sub_dataset=None, extension=None):
        super().__init__(spark, sc, glueContext, dataset, 'preparation')
        self.spark.conf.set("spark.sql.shuffle.partitions", "1") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.spark.conf.set('spark.sql.caseSensitive', True)
        self.extension = extension
        self.sub_dataset = sub_dataset
        self.file_path = f"service_agent_server_files/uploads/{sub_dataset}"
        self.list_of_files = self.aws_instance.get_files_in_s3_path(f"{self.raw_bucket_name}/{self.file_path}")

    def get_data(self):
        if self.extension == 'xml':
            root_tag = self.extract_root_tag(self.raw_bucket_name, f'{self.file_path}/')
            if not root_tag:
                raise ValueError(f"Unable to infer XML root tag from '{self.raw_bucket_name}/{self.file_path}/'. ")
            self.logger.info(f"Root tag: {root_tag}")
            df = self.read_data_from_s3(self.raw_bucket_name, self.file_path, 'xml', row_tag=root_tag)

        elif self.extension == 'csv':
            df = self.read_data_from_s3(self.raw_bucket_name, self.file_path, 'csv')

        else:
            raise ValueError(f"Unsupported file extension '{self.extension}'. Supported extensions are: 'xml', 'csv'.")

        return df

    def transform_data(self, df): 
        """
        Transform the given DataFrame.

        This method executes the following steps:        
        1. Capture the full input file path in 'host_name'
        2. (XML only) Drop unnecessary nested field ("_VALUE")
        3. (XML only) Flatten nested DataFrame structure
        4. (XML only) Convert complex nested columns into JSON strings
        5. Extract file timestamp from input path (UTC)
        6. Extract host folder name
        7. Extract restaurant/site number
        8. Extract device identifier
        9. Remove trailing whitespaces
        10. Add CDC (Change Data Capture) columns



        Parameters:
        - df: Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.

        """
        
        # Step 1: Capture the full input file path in 'host_name' (e.g., '.../subdataset/UK04071GSC01/...').
        df = df.withColumn("host_name", F.input_file_name())

        if self.extension == 'xml':
            new_cols = [c.replace(":", "_") for c in df.columns]
            df = df.toDF(*new_cols)

            # Step 2: Drop unnecessary nested field "_VALUE"
            df = self.drop_nested_field(df, "_VALUE")

            # Step 3: Flatten nested DataFrame structure
            df = self.flatten_nest_df(df)
    
            # Step 4: Convert complex nested types into JSON strings, and cast simple types to string.
            df = df.select(*[
                (F.to_json(F.col(f.name)) if isinstance(f.dataType, (T.ArrayType, T.StructType, T.MapType))
                else F.col(f.name).cast("string")).alias(f.name)
                for f in df.schema.fields
            ])

        # Step 5: Extract and parse in one go (UTC because of the 'Z' in the format)
        df = df.withColumn("ingest_file_timestamp_utc", F.to_timestamp(F.regexp_extract(F.col("host_name"), r"(\d{8}T\d{6}Z)", 1), "yyyyMMdd'T'HHmmss'Z'"))

        # Step 6: Extract the host folder taken out of the path based on sub-dataset structure.
        df = df.withColumn("host_name", F.regexp_extract(F.col("host_name"), rf"{self.sub_dataset}/([^/]+)/", 1))

        # Step 7: Extract the 5-digit site/restaurant number that appears after two leading letters (e.g., 'UK04071GSC01')
        df = df.withColumn("restaurant_number", F.regexp_extract(F.col("host_name"), r"^[A-Za-z]{2}(\d{5})", 1).cast("int"))

        # Step 8: Extract last three letters and two digits from host_name as device
        df = df.withColumn("device_name", F.regexp_extract(F.col("host_name"), r"([A-Za-z]{3}\d{2})$", 1))

        # Step 9: Remove trailing whitespaces
        df = self.remove_trailing_whitespace(df)

        # Step 10: Add CDC (Change Data Capture) columns
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

        #if not self.aws_instance.athena_table_exists('preparation', f'service_agent_{self.sub_dataset}'):

        self.aws_instance.delete_athena_table('preparation', f'service_agent_{self.sub_dataset}')
        
        # Execute Athena query to create the table
        self.aws_instance.create_athena_delta_table('preparation', f'service_agent_{self.sub_dataset}', save_output_path, self.athena_output_path)
        
        # Delete files
        for file_name in self.list_of_files:
            self.aws_instance.delete_s3_object(self.raw_bucket_name, file_name)
        
        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed DQ rules"
            self.aws_instance.send_sns_message(message)
        
        s3_paths = [f"s3://{self.preparation_bucket_name}/{self.file_path}/"]

        self.apply_retention_policy(60, s3_paths)

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

            # Iterate through subfolders until find a file
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
            raise


