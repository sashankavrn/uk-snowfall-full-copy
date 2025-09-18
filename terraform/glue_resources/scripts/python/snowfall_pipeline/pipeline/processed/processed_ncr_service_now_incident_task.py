from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from datetime import datetime

class ProcessedNcrServiceNowIncidentTask(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/incident_task"

    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df

    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Splits datetime column
        2. Filters passed records
        3. Drops unnecessary columns
        4. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
  
        # Step 1: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 2: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 3: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'sys_id': ('sys_id', 'string'),
            'number': ('incident_task_number', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'sys_updated_on': ('sys_updated_timestamp', 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_on_dt': ('sys_updated_date', 'date'),
            'opened_at': ('opened_timestamp', 'string'),
            'opened_at_timestamp': ('opened_timestamp_utc', 'timestamp'),
            'opened_at_dt': ('opened_date', 'date'),
            'opened_by_display_value': ('opened_by', 'string'),
            'active': ('active', 'boolean'),
            'assigned_to_display_value': ('assigned_to', 'string'),
            'assignment_group_display_value': ('assignment_group', 'string'),
            'business_duration': ('business_duration', 'double'),
            'calendar_duration': ('calendar_duration', 'double'),
            'close_notes': ('close_notes', 'string'),
            'closed_at': ('closed_timestamp', 'string'),
            'closed_at_timestamp': ('closed_timestamp_utc', 'timestamp'),
            'closed_at_dt': ('closed_date', 'date'),
            'closed_by_display_value': ('closed_by', 'string'),
            'correlation_display': ('correlation_display', 'string'),
            'correlation_id': ('correlation_id', 'string'),
            'description': ('description', 'string'),
            'due_date': ('due_timestamp', 'string'),
            'due_date_timestamp': ('due_timestamp_utc', 'timestamp'),
            'due_date_dt': ('due_date', 'date'),
            'escalation': ('escalation', 'string'),
            'expected_start': ('expected_start_timestamp', 'string'),
            'expected_start_timestamp': ('expected_start_timestamp_utc', 'timestamp'),
            'expected_start_dt': ('expected_start_date', 'date'),
            'incident_display_value': ('incident_number', 'string'),
            'incident_id': ('incident_id', 'string'),
            'made_sla': ('made_sla', 'boolean'),
            'priority': ('priority', 'string'),
            'reassignment_count': ('reassignment_count', 'integer'),
            'short_description_display_value': ('short_description', 'string'),
            'state_display_value': ('state', 'string'),
            'sys_mod_count': ('sys_mod_count', 'integer'),
            'u_external_url': ('u_external_url', 'string'),
            'u_parts_in': ('u_parts_in', 'string'),
            'u_parts_out': ('u_parts_out', 'string'),
            'u_resolution_notes': ('u_resolution_notes', 'string'),
            'u_task_assigned_on': ('u_task_assigned_timestamp', 'string'),
            'u_task_assigned_on_timestamp': ('u_task_assigned_timestamp_utc', 'timestamp'),
            'u_task_assigned_on_dt': ('u_task_assigned_date', 'date'),
            'u_third_party_sla': ('u_third_party_sla_timestamp', 'string'),
            'u_third_party_sla_timestamp': ('u_third_party_sla_timestamp_utc', 'timestamp'),
            'u_third_party_sla_dt': ('u_third_party_sla_date', 'date'),
            'u_third_party_state': ('u_third_party_state', 'string'),
            'work_end': ('work_end_timestamp', 'string'),
            'work_end_timestamp': ('work_end_timestamp_utc', 'timestamp'),
            'work_end_dt': ('work_end_date', 'date'),
            'work_start': ('work_start_timestamp', 'string'),
            'work_start_timestamp': ('work_start_timestamp_utc', 'timestamp'),
            'work_start_dt': ('work_start_date', 'date'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_created_year': ('sys_created_year', 'integer'),
            'sys_created_month': ('sys_created_month', 'integer')
        }

        # Step 4: Changes column names and schema
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

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_incident_task'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_incident_task', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
