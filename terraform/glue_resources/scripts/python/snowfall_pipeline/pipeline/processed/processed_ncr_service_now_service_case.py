from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowServiceCase(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/service_case"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Decode HTML entities in specified columns
        2. Adds case type based on restaurant number
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

        # Step 2: Adds case type based on restaurant number
        df = df.withColumn("case_type", F.when(F.col("restaurant_number") != -1, "Store").otherwise("Corporate"))

        # Step 3: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 4: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 5: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'sys_id': ('sys_id', 'String'),
            'restaurant_number': ('restaurant_id', 'Integer'),
            'number': ('case_number', 'string'),
            'case_type': ('case_type', 'string'),
            'account_name': ('account_name', 'String'),
            'asset': ('asset', 'String'),
            'category': ('category', 'String'),
            'active_account_escalation': ('active_account_escalation', 'String'),
            'active_escalation': ('active_escalation', 'String'),
            'assigned_on_timestamp': ('assigned_timestamp_utc', 'Timestamp'),
            'assigned_on': ('assigned_timestamp', 'String'),
            'assigned_on_dt': ('assigned_date', 'Date'),
            'u_call_type': ('u_call_type', 'String'),
            'u_caller_email': ('u_caller_email', 'String'),
            'case': ('case', 'String'),
            'u_case_reassigned': ('u_case_reassigned', 'boolean'),
            'u_case_reopened': ('u_case_reopened', 'boolean'),
            'case_report': ('case_report', 'String'),
            'cause': ('cause', 'String'),
            'contact': ('contact', 'String'),
            'entitlement': ('entitlement', 'String'),
            'first_response_time_timestamp': ('first_response_timestampt_utc', 'Timestamp'),
            'first_response_time': ('first_response_timestamp', 'String'),
            'first_response_time_dt': ('first_response_date', 'Date'),
            'incident': ('incident', 'String'),
            'initiated_as_request': ('initiated_as_request', 'boolean'),
            'internal_contact': ('internal_contact', 'String'),
            'major_case_state': ('major_case_state', 'String'),
            'u_number_of_reassignments': ('u_number_of_reassignments', 'integer'),
            'u_number_of_reopens': ('u_number_of_reopens', 'integer'),
            'u_pending_reason': ('u_pending_reason', 'String'),
            'problem': ('problem', 'String'),
            'product': ('product', 'String'),
            'resolution_code': ('resolution_code', 'String'),
            'resolved_at_timestamp': ('resolved_timestamp_utc', 'Timestamp'),
            'resolved_at': ('resolved_timestamp', 'String'),
            'resolved_at_dt': ('resolved_date', 'Date'),
            'resolved_by': ('resolved_by', 'String'),
            'subcategory': ('subcategory', 'String'),
            'action_status': ('action_status', 'String'),
            'active': ('active', 'boolean'),
            'business_duration': ('business_duration', 'String'),
            'business_service': ('business_service', 'String'),
            'close_notes': ('close_notes', 'String'),
            'closed_at_timestamp': ('closed_timestamp_utc', 'Timestamp'),
            'closed_at': ('closed_timestamp', 'String'),
            'closed_at_dt': ('closed_date', 'Date'),
            'closed_by': ('closed_by', 'String'),
            'contact_type': ('contact_type', 'String'),
            'correlation_id': ('correlation_id', 'String'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'Timestamp'),
            'sys_created_on': ('sys_created_timestamp', 'String'),
            'sys_created_on_dt': ('sys_created_date', 'Date'),
            'sys_created_by': ('sys_created_by', 'String'),
            'description': ('description', 'String'),
            'knowledge': ('knowledge', 'boolean'),
            'calendar_duration': ('calendar_duration', 'String'),
            'escalation': ('escalation', 'String'),
            'impact': ('impact', 'String'),
            'made_sla': ('made_sla', 'boolean'),
            'needs_attention': ('needs_attention', 'boolean'),
            'opened_at_timestamp': ('opened_timestamp_utc', 'Timestamp'),
            'opened_at': ('opened_timestamp', 'String'),
            'opened_at_dt': ('opened_date', 'Date'),
            'opened_by': ('opened_by', 'String'),
            'priority': ('priority', 'String'),
            'reassignment_count': ('reassignment_count', 'integer'),
            'service_offering': ('service_offering', 'String'),
            'short_description': ('short_description', 'String'),
            'state': ('state', 'String'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'Timestamp'),
            'sys_updated_on': ('sys_updated_timestamp', 'String'),
            'sys_updated_on_dt': ('sys_updated_date', 'Date'),
            'sys_updated_by': ('sys_updated_by', 'String'),
            'sys_mod_count': ('sys_mod_count', 'integer'),
            'urgency': ('urgency', 'String'),
            'assignment_group__name': ('assignment_group_name', 'String'),
            'assignment_group__sys_id': ('assignment_group_sys_id', 'String'),
            'assigned_to__name': ('assigned_to_name', 'String'),
            'assigned_to__sys_id': ('assigned_to_sys_id', 'String'),
            'parent__number': ('parent_number', 'String'),
            'parent__sys_id': ('parent_sys_id', 'String'),
            'product__name': ('product_name', 'String'),
            'assignment_group__manager': ('assignment_group_manager', 'String'),
            'eventprocessedutctime_timestamp': ('event_processed_timestamp_utc', 'Timestamp'),
            'eventprocessedutctime': ('event_processed_timestamp', 'String'),
            'eventprocessedutctime_dt': ('event_processed_date', 'Date'),
            'eventenqueuedutctime_timestamp': ('event_enqueued_timestamp_utc', 'Timestamp'),
            'eventenqueuedutctime': ('event_enqueued_timestamp', 'String'),
            'eventenqueuedutctime_dt': ('event_enqueued_date', 'Date'),
            'category_id': ('category_id', 'String'),
            'resolution_code_id': ('resolution_code_id', 'String'),
            'resolution_code_value': ('resolution_code_value', 'String'),
            'subcategory_id': ('subcategory_id', 'String'),
            'impact_id': ('impact_id', 'integer'),
            'priority_id': ('priority_id', 'integer'),
            'state_id': ('state_id', 'integer'),
            'urgency_id': ('urgency_id', 'integer'),
            'u_issue_type_value': ('u_issue_type_value', 'String'),
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

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_service_case'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_service_case', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
