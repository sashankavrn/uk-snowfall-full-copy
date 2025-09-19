from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowChangeRequest(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/change_request"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Decode HTML entities
        2. Split the 'u_account' column by commas and create a new row for each value
        3.  Extract restaurant number from u_account
        4. Fill null values in specified column
        5. Add change request type based on restaurant number
        6. Splits datetime column
        7. Filters passed records
        8. Drops unnecessary columns
        9. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """

        # Step 1: Decode HTML entities in specified columns
        df = self.html_entity_decoder(df, self.pipeline_config.get('html_entity_columns'))

        # Step 2: Split the 'u_account' column by commas and create a new row for each value
        df = df.withColumn("u_account", F.explode_outer(F.split("u_account", ",\s*")))

        # Stpe 3: Extract restaurant number from u_account
        df = self.parse_column_values(df, self.pipeline_config.get('new_column_params'))

        # Stpe 4: Fill null values in specified column
        df = self.replace_value(df, self.pipeline_config.get('replace_values'))

        # Step 5: Adds change request type based on restaurant number
        df = df.withColumn("change_request_type", F.when(F.col("restaurant_id") != -1, "Store").otherwise("Corporate"))

        # Step 6: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 7: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 8: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'number': ('change_request_number', 'string'),
            'restaurant_id': ('restaurant_id', 'integer'),
            'change_request_type': ('change_request_type', 'string'),
            'state': ('state', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'sys_updated_on': ('sys_updated_timestamp', 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_on_dt': ('sys_updated_date', 'date'),
            'active': ('active', 'boolean'),
            'assigned_to': ('assigned_to', 'string'),
            'assignment_group': ('assignment_group', 'string'),
            'backout_plan': ('backout_plan', 'string'),
            'business_service': ('business_service', 'string'),
            'cab_date': ('cab_date', 'string'),
            'cab_recommendation': ('cab_recommendation', 'string'),
            'cab_required': ('cab_required', 'boolean'),
            'calendar_duration': ('calendar_duration', 'string'),
            'category': ('category', 'string'),
            'chg_model': ('chg_model', 'string'),
            'close_code': ('close_code', 'string'),
            'close_notes': ('close_notes', 'string'),
            'closed_at': ('closed_timestamp', 'string'),
            'closed_at_timestamp': ('closed_timestamp_utc', 'timestamp'),
            'closed_at_dt': ('closed_date', 'date'),
            'closed_by': ('closed_by', 'string'),
            'description': ('description', 'string'),
            'end_date': ('end_timestamp', 'string'),
            'end_date_timestamp': ('end_timestamp_utc', 'timestamp'),
            'end_date_dt': ('end_date', 'date'),
            'implementation_plan': ('implementation_plan', 'string'),
            'justification': ('justification', 'string'),
            'knowledge': ('knowledge', 'boolean'),
            'opened_at': ('opened_timestamp', 'string'),
            'opened_at_timestamp': ('opened_timestamp_utc', 'timestamp'),
            'opened_at_dt': ('opened_date', 'date'),
            'opened_by': ('opened_by', 'string'),
            'reassignment_count': ('reassignment_count', 'integer'),
            'requested_by': ('requested_by', 'string'),
            'requested_by_first_name': ('requested_by_first_name', 'string'),
            'requested_by_last_name': ('requested_by_last_name', 'string'),
            'review_comments': ('review_comments', 'string'),
            'risk': ('risk', 'string'),
            'risk_impact_analysis': ('risk_impact_analysis', 'string'),
            'service_offering': ('service_offering', 'string'),
            'short_description': ('short_description', 'string'),
            'start_date': ('start_timestamp', 'string'),
            'start_date_timestamp': ('start_timestamp_utc', 'timestamp'),
            'start_date_dt': ('start_date', 'date'),
            'sys_id': ('sys_id', 'string'),
            'sys_mod_count': ('sys_mod_count', 'integer'),
            'test_plan': ('test_plan', 'string'),
            'type': ('type', 'string'),
            'u_account': ('u_account', 'string'),
            'u_additional_approvers': ('u_additional_approvers', 'string'),
            'u_impacted_area': ('u_impacted_area', 'string'),
            'u_jira_number': ('u_jira_number', 'string'),
            'u_post_implementation_validation_plan': ('u_post_implementation_validation_plan', 'string'),
            'u_sub_category': ('u_sub_category', 'string'),
            'u_test_approver': ('u_test_approver', 'string'),
            'u_test_qa_environment': ('u_test_qa_environment', 'string'),
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

        # Step 9: Changes column names and schema
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

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_change_request'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_change_request', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
