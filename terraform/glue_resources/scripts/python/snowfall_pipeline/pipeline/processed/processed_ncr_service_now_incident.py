from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowIncident(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/incident"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1: Adds incident type based on restaurant number
        2: Extracts Vista dispatch number from work notes
        3: Adds 'P' prefix to priority_id to create priority label
        4. Splits datetime column
        5. Filters passed records
        6. Drops unnecessary columns
        7. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
        
        # Step 1: Adds incident type based on restaurant number
        df = df.withColumn("incident_type", F.when(F.col("restaurant_number") != -1, "Store").otherwise("Corporate"))


        # Step 2: Extracts Vista dispatch number from work notes
        df = df.withColumn("vista_dispatch_number", F.when(
                F.col("work_notes").rlike(r"Vista dispatch request number (\d+) received\."),
                F.regexp_extract("work_notes", r"Vista dispatch request number (\d+) received\.", 1)
            )
        )


        # Step 3: Adds 'P' prefix to priority_id to create priority label
        #df = df.withColumn("priority", F.concat(F.lit("P"), F.col("priority_id")))
  
        # Step 4: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 5: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['created_year','created_month'])

        # Step 6: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'sys_id': ('sys_id', 'string'),
            'restaurant_number': ('restaurant_id', 'Integer'),
            'number': ('incident_number', 'string'),
            'incident_type': ('incident_type', 'string'),
            'vista_dispatch_number': ('u_vista_id', 'string'),
            'opened_at_timestamp': ('opened_timestamp_utc', 'timestamp'),
            'opened_at': ('opened_timestamp', 'string'),
            'opened_at_dt': ('opened_date', 'date'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_on': ('sys_updated_timestamp', 'string'),
            'sys_updated_on_dt': ('sys_updated_date', 'date'),
            'description': ('description', 'string'),
            'short_description_display_value': ('short_description', 'string'),
            'comments': ('comments', 'string'),
            'work_notes': ('work_notes', 'string'),
            'comments_and_work_notes': ('comments_and_work_notes', 'string'),
            'close_notes': ('close_notes', 'string'),
            'incident_state_display_value': ('state', 'string'),
            'business_impact': ('business_impact', 'string'),
            'severity_display_value': ('severity_display_value', 'string'),
            'active': ('active_flag', 'boolean'),
            'state_display_value': ('state_display_value', 'string'),
            'assigned_to_display_value': ('assigned_to', 'string'),
            'assigned_to_id': ('assigned_to_id', 'string'),
            'assignment_group_display_value': ('assignment_group', 'string'),
            'assignment_group_id': ('assignment_group_id', 'string'),
            'business_duration': ('business_duration', 'double'),
            'business_service_display_value': ('business_service', 'string'),
            'business_service_id': ('business_service_id', 'string'),
            'business_stc': ('business_duration_seconds', 'string'),
            'calendar_duration': ('calendar_duration', 'double'),
            'calendar_stc': ('calendar_stc', 'string'),
            'caller_id_display_value': ('caller_id', 'string'),
            'caller_id_id': ('caller_id_id', 'string'),
            'category_display_value': ('category', 'string'),
            'category_id': ('category_id', 'string'),
            'child_incidents': ('child_incidents_count', 'string'),
            'close_code_display_value': ('close_code', 'string'),
            'close_code_id': ('close_code_id', 'string'),
            'closed_at_timestamp': ('closed_timestamp_utc', 'timestamp'),
            'closed_at': ('closed_timestamp', 'string'),
            'closed_at_dt': ('closed_date', 'date'),
            'closed_by_display_value': ('closed_by', 'string'),
            'closed_by_id': ('closed_by_id', 'string'),
            'cmdb_ci_business_app_display_value': ('cmdb_ci_business_app_display_value', 'string'),
            'cmdb_ci_business_app_id': ('cmdb_ci_business_app_id', 'string'),
            'cmdb_ci_display_value': ('cmdb_ci_display_value', 'string'),
            'cmdb_ci_id': ('cmdb_ci_id', 'string'),
            'contact_type_display_value': ('contact_type', 'string'),
            'contact_type_id': ('contact_type_id', 'string'),
            'correlation_display': ('correlation_display', 'string'),
            'correlation_id': ('correlation_id', 'string'),
            'escalation': ('escalation', 'string'),
            'expected_start_timestamp': ('expected_start_timestamp_utc', 'timestamp'),
            'expected_start': ('expected_start_timestamp', 'string'),
            'expected_start_dt': ('expected_start_date', 'date'),
            'follow_up_timestamp': ('follow_up_timestamp_utc', 'timestamp'),
            'follow_up': ('follow_up_timestamp', 'string'),
            'follow_up_dt': ('follow_up_date', 'date'),
            'hold_reason_display_value': ('hold_reason', 'string'),
            'hold_reason_id': ('hold_reason_id', 'string'),
            'priority': ('priority', 'string'),
            'incident_state_id': ('incident_state_id', 'string'),
            'knowledge': ('knowledge', 'string'),
            'lessons_learned': ('lessons_learned', 'string'),
            'made_sla': ('made_sla', 'string'),
            'major_incident_state_display_value': ('major_incident_state_display_value', 'string'),
            'major_incident_state_id': ('major_incident_state_id', 'string'),
            'needs_attention': ('needs_attention', 'string'),
            'opened_by_display_value': ('opened_by', 'string'),
            'opened_by_id': ('opened_by_id', 'string'),
            'parent_display_value': ('parent_display_value', 'string'),
            'parent_id': ('parent', 'string'),
            'parent_incident_display_value': ('parent_incident_number', 'string'),
            'parent_incident_id': ('parent_incident_id', 'string'),
            'problem_id_display_value': ('problem_id_number', 'string'),
            'problem_id_id': ('problem_id_id', 'string'),
            'promoted_on_timestamp': ('promoted_timestamp_utc', 'timestamp'),
            'promoted_on': ('promoted_timestamp', 'string'),
            'promoted_on_dt': ('promoted_date', 'date'),
            'proposed_on_timestamp': ('proposed_timestamp_utc', 'timestamp'),
            'proposed_on': ('proposed_timestamp', 'string'),
            'proposed_on_dt': ('proposed_date', 'date'),
            'reassignment_count': ('reassignment_count', 'int'),
            'reopen_count': ('reopen_count', 'int'),
            'reopened_by_display_value': ('reopened_by', 'string'),
            'reopened_by_id': ('reopened_by_id', 'string'),
            'reopened_time_timestamp': ('reopened_timestamp_utc', 'timestamp'),
            'reopened_time': ('reopened_timestamp', 'string'),
            'reopened_time_dt': ('reopened_time_date', 'date'),
            'resolved_at_timestamp': ('resolved_at_timestamp_utc', 'timestamp'),
            'resolved_at': ('resolved_at_timestamp', 'string'),
            'resolved_at_dt': ('resolved_at_date', 'date'),
            'resolved_by_display_value': ('resolved_by', 'string'),
            'resolved_by_id': ('resolved_by_id', 'string'),
            'service_offering_display_value': ('service_offering', 'string'),
            'service_offering_id': ('service_offering_id', 'string'),
            'severity_id': ('severity_id', 'string'),
            'short_description_id': ('short_description_id', 'string'),
            'state_id': ('state_id', 'string'),
            'subcategory_display_value': ('subcategory', 'string'),
            'subcategory_id': ('subcategory_id', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_mod_count': ('sys_mod_count', 'int'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'task_effective_number': ('task_effective_number', 'string'),
            'u_asset_display_value': ('u_asset_display_value', 'string'),
            'u_asset_id': ('u_asset_id', 'string'),
            'u_assigned_to_qlid': ('u_assigned_to_qlid', 'string'),
            'u_awareness_of_customer_impact_timestamp': ('u_awareness_of_customer_impact_timestamp_utc', 'timestamp'),
            'u_awareness_of_customer_impact': ('u_awareness_of_customer_impact_timestamp', 'string'),
            'u_awareness_of_customer_impact_dt': ('u_awareness_of_customer_impact_date', 'date'),
            'u_cause_code_display_value': ('u_cause_code_display_value', 'string'),
            'u_cause_code_id': ('u_cause_code_id', 'string'),
            'u_incident_management_invoked_timestamp': ('u_incident_management_invoked_timestamp_utc', 'timestamp'),
            'u_incident_management_invoked': ('u_incident_management_invoked_timestamp', 'string'),
            'u_incident_management_invoked_dt': ('u_incident_management_invoked_date', 'date'),
            'u_internal_communication_timestamp': ('u_internal_communication_timestamp_utc', 'timestamp'),
            'u_internal_communication': ('u_internal_communication_timestamp', 'string'),
            'u_internal_communication_dt': ('u_internal_communication_date', 'date'),
            'u_on_call_paging_time_timestamp': ('u_on_call_paging_timestamp_utc', 'timestamp'),
            'u_on_call_paging_time': ('u_on_call_paging_timestamp', 'string'),
            'u_on_call_paging_time_dt': ('u_on_call_paging_date', 'date'),
            'u_product_name_display_value': ('u_product_name_display_value', 'string'),
            'u_product_name_id': ('u_product_name_id', 'string'),
            'u_record_source_display_value': ('u_record_source_display_value', 'string'),
            'u_record_source_id': ('u_record_source_id', 'string'),
            'u_rpt_response_duration': ('u_rpt_response_duration', 'double'),
            'u_site_display_value': ('u_site_display_value', 'string'),
            'u_site_id': ('u_site_id', 'string'),
            'u_task_assigned_on_timestamp': ('u_task_assigned_timestamp_utc', 'timestamp'),
            'u_task_assigned_on': ('u_task_assigned_timestamp', 'string'),
            'u_task_assigned_on_dt': ('u_task_assigned_date', 'date'),
            'u_was_a_monitoring_alerts_received': ('u_was_a_monitoring_alerts_received', 'string'),
            'u_customer_contact_display_value': ('u_customer_contact_display_value', 'string'),
            'u_customer_contact_id': ('u_customer_contact_id', 'string'),
            'u_kb_article_used_for_resolution_display_value': ('u_related_kb_article', 'string'),
            'u_kb_article_used_for_resolution_id': ('u_kb_article_used_for_resolution_id', 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_created_year': ('sys_created_year', 'int'),
            'sys_created_month': ('sys_created_month', 'int')
        }

        # Step 7. Changes column names and schema
        df = self.change_column_names_and_schema(df, column_mapping)

        return df

    def save_data(self, df):
            """
            Save DataFrame to an S3 location and create/update a Delta table if needed.

            Parameters:
            - df (DataFrame): Input DataFrame to be saved.

            """
            # Define the S3 save path
            # save_output_path = f"s3://{self.processed_bucket_name}/{self.file_path}/"

            # # Check if Delta table needs to be created
            # if DeltaTable.isDeltaTable(self.spark,save_output_path) is False:
            #     self.athena_trigger = True
                
            # # Determine whether to create or merge to the Delta table
            # if self.athena_trigger:
            #     # Create the Delta table
            #     df.write.format("delta").mode("overwrite") \
            #     .partitionBy('sys_created_year','sys_created_month') \
            #     .save(save_output_path)
                
            # else:
            #     # Append the Delta table
            #     df.write.format("delta").mode("append") \
            #     .save(save_output_path)

            #     # Vacuum the table
            #     self.vacuum_table(save_output_path,48)

            # if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_incident'):
            #     # Execute Athena query to create the table
            #     self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_incident', save_output_path, self.athena_output_path)

            # # If error detected from DQ failing then will raise
            # if self.sns_trigger:
            #     message = "Records in the error folder that have failed transformation"
            #     self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
