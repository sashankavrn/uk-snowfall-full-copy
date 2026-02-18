from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from datetime import datetime

class ProcessedNcrServiceNowIncidentSla(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/incident_sla"

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
            'sys_id': ('sys_id', 'string'),
            'sla_id': ('sla_id', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'sys_updated_on': ('sys_updated_timestamp', 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_on_dt': ('sys_updated_date', 'date'),
            'pause_duration': ('pause_duration', 'double'),
            'pause_time': ('pause_time', 'timestamp'),
            'timezone': ('timezone', 'string'),
            'u_assigned_to_when_breached_id': ('u_assigned_to_when_breached_id', 'string'),
            'u_assigned_to_when_breached_display_value': ('u_assigned_to_when_breached', 'string'),
            'business_time_left': ('business_time_left', 'double'),
            'duration': ('duration', 'double'),
            'time_left': ('time_left', 'double'),
            'business_duration': ('business_duration', 'double'),
            'percentage': ('percentage', 'double'),
            'original_breach_time': ('original_breach_time', 'timestamp'),
            'business_percentage': ('business_percentage', 'double'),
            'sys_mod_count': ('sys_mod_count', 'integer'),
            'active': ('active', 'string'),
            'sla_display_value': ('sla', 'string'),
            'business_pause_duration': ('business_pause_duration', 'double'),
            'sys_tags': ('sys_tags', 'string'),
            'schedule_id': ('schedule_id', 'string'),
            'schedule_display_value': ('schedule', 'string'),
            'task_id': ('task_id', 'string'),
            'task_display_value': ('task', 'string'),
            'stage_id': ('stage_id', 'string'),
            'stage_display_value': ('stage', 'string'),
            'u_group_when_breached_id': ('u_group_when_breached_id', 'string'),
            'u_group_when_breached_display_value': ('u_group_when_breached', 'string'),
            'planned_end_time': ('planned_end_time', 'timestamp'),
            'has_breached': ('has_breached', 'string'),
            'task__assignment_group_id': ('task_assignment_group_id', 'string'),
            'task__assignment_group_value': ('task_assignment_group', 'string'),
            'task__description': ('task_description', 'string'),
            'task__parent_id': ('task_parent_id', 'string'),
            'task__parent_value': ('task_parent', 'string'),
            'end_time': ('end_time_timestamp', 'string'),
            'end_time_timestamp': ('end_time_timestamp_utc', 'timestamp'),
            'end_time_dt': ('end_time_date', 'date'),
            'start_time': ('start_time_timestamp', 'string'),
            'start_time_timestamp': ('start_time_timestamp_utc', 'timestamp'),
            'start_time_dt': ('start_time_date', 'date'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_created_year': ('sys_created_year', 'integer'),
            'sys_created_month': ('sys_created_month', 'integer')
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

        if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_incident_sla'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_incident_sla', save_output_path, self.athena_output_path)

        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed transformation"
            self.aws_instance.send_sns_message(message)

        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
