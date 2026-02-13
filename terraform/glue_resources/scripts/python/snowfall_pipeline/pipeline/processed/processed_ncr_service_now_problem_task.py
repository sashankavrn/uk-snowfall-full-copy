from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowProblemTask(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/problem_task"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1: Check if DataFrame is empty
        2. Decode HTML entities in specified columns
        3. Remove HTML tags from specified string columns
        4. Splits datetime column
        5. Filters passed records
        6. Drops unnecessary columns
        7. Change column names and schema.

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
        
        # Step 2: Decode HTML entities in specified columns
        #df = self.html_entity_decoder(df, self.pipeline_config.get('html_entity_columns'))

        # Step 3: Remove HTML tags from specified string columns
        #df = self.strip_html_tags (df, self.pipeline_config.get('html_tag_columns'))

        # Step 4: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 5: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 6: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'number': ('problem_task_number', 'string'), 
            'problem_task_type_id': ('problem_task_type_id', 'string'), 
            'problem_task_type_display_value': ('problem_task_type', 'string'), 
            'sys_created_on': ('sys_created_timestamp' , 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc' , 'timestamp'),
            'sys_created_on_dt': ('sys_created_date' , 'date'),
            'opened_at': ('opened_timestamp' , 'string'),
            'opened_at_timestamp': ('opened_timestamp_utc' , 'timestamp'),
            'opened_at_dt': ('opened_date' , 'date'),
            'sys_updated_on': ('sys_updated_timestamp' , 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc' , 'timestamp'),
            'sys_updated_on_dt': ('sys_updated_date' , 'date'),
            'problem_id': ('problem_id', 'string'), 
            'problem_display_value': ('problem_number', 'string'), 
            'state_display_value': ('state', 'string'), 
            'sys_created_by': ('sys_created_by', 'string'), 
            'knowledge': ('knowledge', 'string'), 
            'impact': ('impact', 'string'), 
            'active': ('active', 'string'), 
            'u_jira': ('u_jira', 'string'), 
            'priority': ('priority', 'string'), 
            'started_at': ('started_at', 'timestamp'), 
            'approval_set': ('approval_set', 'timestamp'), 
            'needs_attention': ('needs_attention', 'string'), 
            'short_description': ('short_description', 'string'), 
            'work_start': ('work_start', 'timestamp'), 
            'follow_up': ('follow_up', 'timestamp'), 
            'reopened_by_id': ('reopened_by_id', 'string'), 
            'reopened_by_display_value': ('reopened_by', 'string'), 
            'reassignment_count': ('reassignment_count', 'string'), 
            'started_by_id': ('started_by_id', 'string'), 
            'started_by_display_value': ('started_by', 'string'), 
            'assigned_to_id': ('assigned_to_id', 'string'), 
            'assigned_to_display_value': ('assigned_to', 'string'), 
            'sla_due': ('sla_due', 'string'), 
            'comments_and_work_notes': ('comments_and_work_notes', 'string'), 
            'u_category_id': ('u_category_id', 'string'), 
            'u_category_display_value': ('u_category', 'string'), 
            'escalation': ('escalation', 'string'), 
            'made_sla': ('made_sla', 'string'), 
            'sys_updated_by': ('sys_updated_by', 'string'), 
            'opened_by_id': ('opened_by_id', 'string'), 
            'opened_by_display_value': ('opened_by', 'string'), 
            'closed_at': ('closed_timestamp' , 'string'),
            'closed_at_timestamp': ('closed_timestamp_utc' , 'timestamp'),
            'closed_at_dt': ('closed_date' , 'date'),            
            'u_rca_task': ('u_rca_task', 'string'), 
            'expected_start': ('expected_start', 'timestamp'), 
            'work_end': ('work_end', 'timestamp'), 
            'work_notes': ('work_notes', 'string'), 
            'reopened_at': ('reopened_timestamp' , 'string'),
            'reopened_at_timestamp': ('reopened_timestamp_utc' , 'timestamp'),
            'reopened_at_dt': ('reopened_date' , 'date'), 
            'assignment_group_id': ('assignment_group_id', 'string'), 
            'assignment_group_display_value': ('assignment_group', 'string'), 
            'description': ('description', 'string'), 
            'sys_id': ('sys_id', 'string'), 
            'contact_type': ('contact_type', 'string'), 
            'urgency': ('urgency', 'string'), 
            'u_auto_close_by_company': ('u_auto_close_by_company', 'string'), 
            'u_task_assigned_on': ('u_task_assigned_on', 'timestamp'), 
            'activity_due': ('activity_due', 'string'), 
            'approval': ('approval', 'string'), 
            'u_impacted_area': ('u_impacted_area', 'string'), 
            'due_date': ('due_date', 'timestamp'), 
            'sys_mod_count': ('sys_mod_count', 'integer'), 
            'reopen_count': ('reopen_count', 'integer'), 
            'cdc_timestamp': ('cdc_timestamp' , 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc' , 'timestamp'),
            'cdc_timestamp_dt': ('cdc_date' , 'date'),
            'sys_created_year': ('sys_created_year', 'integer'), 
            'sys_created_month': ('sys_created_month', 'integer')
        }

        # Step 7: Changes column names and schema
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

        if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_problem_task'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_problem_task', save_output_path, self.athena_output_path)

        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed transformation"
            self.aws_instance.send_sns_message(message)

        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
