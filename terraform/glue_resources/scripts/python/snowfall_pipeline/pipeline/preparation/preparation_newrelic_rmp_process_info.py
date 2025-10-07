from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.data_quality_rules import dq_rules
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class PreparationNewrelicRmpProcessInfo(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.pipeline_config = self.full_configs[self.datasets]
        self.dq_rule = dq_rules.get(self.datasets)
        self.file_path = "newrelic/newrelic_rmp_process_info"
        self.list_of_files = self.aws_instance.get_files_in_s3_path(f"{self.raw_bucket_name}/{self.file_path}/")


    def get_data(self):
        df = self.read_data_from_s3(self.raw_bucket_name,self.file_path,'json', multiline_json = True)
        return df

    def transform_data(self, df): 
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Convert latest_timestamp from milliseconds to readable datetime
        2. Create new columns based on configuration
        3. Fill null values in specified column
        4. Remove duplicate records.
        5. Remove trailing whitespaces
        6. Perform data quality check.
        7. Add CDC columns.

        Parameters:
        - df: Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.

        """
        
        # Step 1: Convert latest_timestamp from milliseconds to readable datetime
        df = df.withColumn("new_relic_timestamp_latest", F.from_unixtime((F.col("new_relic_timestamp_latest") / 1000).cast("long")))

        # Step 2: Create new columns based on configuration
        df = self.parse_column_values(df, self.pipeline_config.get('new_column_params'))

        # Stpe 3: Fill null values in specified column
        df = self.replace_value(df, self.pipeline_config.get('replace_values'))

        # Step 4: Remove duplicate records
        df = self.dropping_duplicates(df)

        # Step 5: Removes trailing whitespaces
        df = self.remove_trailing_whitespace(df)

        # Step 6: Data quality check
        df = self.data_quality_check(df, self.dq_rule,self.pipeline_config.get('primary_key'), self.raw_bucket_name, self.file_path, 'json')  

        # Step 7: Add CDC columns
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

        # Check if Athena table needs to be created
        if not self.aws_instance.athena_table_exists('preparation', 'newrelic_rmp_process_info'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('preparation', 'newrelic_rmp_process_info', save_output_path, self.athena_output_path)
        
        # Delete files
        for file_name in self.list_of_files:
            self.aws_instance.delete_s3_object(self.raw_bucket_name, file_name)
        
        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed DQ rules"
            self.aws_instance.send_sns_message(message)
        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
