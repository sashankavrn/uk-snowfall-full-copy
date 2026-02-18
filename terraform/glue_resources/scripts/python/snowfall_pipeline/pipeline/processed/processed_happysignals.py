from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable

class ProcessedHappysignals(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "happysignals"

    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df

    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Check if DataFrame is empty
        2. Splits datetime column
        3. Filters passed records
        4. Drops unnecessary columns
        5. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
        # Step 1: Check if DataFrame is empty
        if not df.head(1):
            self.logger.warning(f"No data found in source '{self.file_path}'. Skipping transformation and exiting workflow.")
            self.sns_trigger = False  # Prevent SNS alert
            return None
          
        # Step 2: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 3: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 4: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'number': ('number', 'string'),
            'score': ('score', 'integer'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'answered_timestamp': ('answered_timestamp_utc', 'timestamp'),
            'answered': ('answered_timestamp', 'string'),
            'answered_dt': ('answered_date', 'date'),
            'class_name': ('class_name', 'string'),
            'closing_assignment_group_display_value': ('closing_assignment_group','string'),
            'closing_assignment_group_id': ('closing_assignment_group_id', 'string'),
            'factors': ('factors', 'string'),
            'feedback_text': ('feedback_text', 'string'),
            'lost_work_time': ('lost_work_time', 'double'),
            'mood': ('mood', 'string'),
            'profile': ('profile', 'string'),
            'related_assignment_groups': ('related_assignment_groups', 'string'),
            'related_user_display_value': ('related_user_display_value', 'string'),
            'related_user_id': ('related_user_id', 'string'),
            'related_users': ('related_users', 'string'),
            'resolved_by_user_display_value': ('resolved_by_user', 'string'),
            'resolved_by_user_id': ('resolved_by_user_id', 'string'),
            'response_id': ('response_id', 'string'),
            'task_display_value': ('case_number', 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_created_year': ('sys_created_year', 'Integer'),
            'sys_created_month': ('sys_created_month', 'Integer')
        }


        # Step 5: Changes column names and schema
        df = self.change_column_names_and_schema(df, column_mapping)

        return df

    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """
        # Check if the DataFrame is None (i.e., no data was returned or it was empty and skipped during transformation)
        if df is None:
            self.logger.info(f"No data to save for '{self.file_path}'. Workflow completed without processing.")
            return
        
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

        if not self.aws_instance.athena_table_exists('processed', 'happysignals'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('processed', 'happysignals', save_output_path, self.athena_output_path)

        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed transformation"
            self.aws_instance.send_sns_message(message)

        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')


