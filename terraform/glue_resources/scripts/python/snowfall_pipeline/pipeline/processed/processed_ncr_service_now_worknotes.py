from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from datetime import datetime

class ProcessedNcrServiceNowWorknotes(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/worknotes"

    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df

    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Decode HTML entities
        2. Remove HTML tags
        3. Splits datetime column
        4. Filters passed records
        5. Drops unnecessary columns
        6. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """

        # Step 1: Decode HTML entities in specified columns
        df = self.html_entity_decoder(df, self.pipeline_config.get('html_entity_columns'))

        # Step 2: Remove HTML tags from specified string columns
        df = self.strip_html_tags (df, self.pipeline_config.get('html_tag_columns'))

        # Step 3: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 4: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 5: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'), 
            'sys_created_on': ('sys_created_timestamp', 'string'), 
            'sys_created_on_dt': ('sys_created_date', 'date'), 
            'sys_created_by': ('sys_created_by', 'string'), 
            'element': ('element', 'string'), 
            'element_id': ('element_id', 'string'), 
            'name': ('name', 'string'), 
            'sys_id': ('sys_id', 'string'), 
            'value': ('value', 'string'), 
            'number': ('number', 'string'), 
            'parent_customer_mcn': ('parent_customer_mcn', 'string'), 
            'parent_customer_name': ('parent_customer_name', 'string'), 
            'parent_customer_sys_id': ('parent_customer_sys_id', 'string'), 
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'), 
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_created_year': ('sys_created_year', 'integer'), 
            'sys_created_month': ('sys_created_month', 'integer')
        }

        # Step 6: Changes column names and schema
        df = self.change_column_names_and_schema(df, column_mapping)

        return df

    def save_data(self, df):
            """
            Save DataFrame to an S3 location and create/update a Delta table if needed.

            Parameters:
            - df (DataFrame): Input DataFrame to be saved.

            """
            # Define the S3 save path
            save_output_path = f"s3://{self.processed_bucket_name}/{self.file_path}/"

            # Check if Delta table needs to be created
            if DeltaTable.isDeltaTable(self.spark,save_output_path) is False:
                self.athena_trigger = True
                
            # Determine whether to create or merge to the Delta table
            if self.athena_trigger:
                # Create the Delta table
                df.write.format("delta").mode("overwrite") \
                .partitionBy('sys_created_year','sys_created_month') \
                .save(save_output_path)
                
            else:
                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_worknotes'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_worknotes', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
