from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowProblemRecord(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/problem_record"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Remove HTML tags from specified string columns
        2. Splits datetime column
        3. Filters passed records
        4. Drops unnecessary columns
        5. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
        # Step 1: Remove HTML tags from specified string columns
        df = self.strip_html_tags (df, self.pipeline_config.get('html_tag_columns'))

        # Step 2: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 3: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 4: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'number': ('problem_record_number', 'string'),
            'sys_created_on': ('sys_created_timestamp' , 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc' , 'timestamp'),
            'sys_created_on_dt': ('sys_created_date' , 'date'),
            'opened_at': ('opened_timestamp' , 'string'),
            'opened_at_timestamp': ('opened_timestamp_utc' , 'timestamp'),
            'opened_at_dt': ('opened_date' , 'date'),
            'sys_updated_on': ('sys_updated_timestamp' , 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc' , 'timestamp'),
            'sys_updated_on_dt': ('sys_updated_date' , 'date'),
            'active': ('active', 'boolean'),
            'assigned_to': ('assigned_to', 'string'),
            'assignment_group': ('assignment_group', 'string'),
            'assignment_group_sys_id': ('assignment_group_sys_id', 'string'),
            'business_duration': ('business_duration', 'string'),
            'business_service': ('business_service', 'string'),
            'calendar_duration': ('calendar_duration', 'string'),
            'category': ('category', 'string'),
            'category_id': ('category_id', 'string'),
            'category_value': ('category_value', 'string'),
            'cause_notes': ('cause_notes', 'string'),
            'close_notes': ('close_notes', 'string'),
            'closed_by': ('closed_by', 'string'),
            'cmdb_ci': ('cmdb_ci', 'string'),
            'confirmed_by': ('confirmed_by', 'string'),
            'country_code': ('country_code', 'string'),
            'delivery_plan': ('delivery_plan', 'string'),
            'description': ('description', 'string'),
            'escalation': ('escalation', 'string'),
            'first_reported_by_task': ('first_reported_by_task', 'string'),
            'fix_by': ('fix_by', 'string'),
            'fix_communicated_by': ('fix_communicated_by', 'string'),
            'fix_notes': ('fix_notes', 'string'),
            'follow_up': ('follow_up', 'string'),
            'knowledge': ('knowledge', 'boolean'),
            'known_error': ('known_error', 'boolean'),
            'made_sla': ('made_sla', 'boolean'),
            'major_problem': ('major_problem', 'boolean'),
            'needs_attention': ('needs_attention', 'boolean'),
            'opened_by': ('opened_by', 'string'),
            'parent': ('parent', 'string'),
            'priority': ('priority', 'string'),
            'reassignment_count': ('reassignment_count', 'integer'),
            'related_incidents': ('related_incidents', 'integer'),
            'reopen_count': ('reopen_count', 'integer'),
            'reopened_by': ('reopened_by', 'string'),
            'resolution_code': ('resolution_code', 'string'),
            'resolved_by': ('resolved_by', 'string'),
            'service_offering': ('service_offering', 'string'),
            'short_description': ('short_description', 'string'),
            'state': ('state', 'string'),
            'subcategory': ('sub_category', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_id': ('sys_id', 'string'),
            'sys_mod_count': ('sys_mod_count', 'string'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'u_business_impact': ('u_business_impact', 'string'),
            'u_customer_description': ('u_customer_description', 'string'),
            'u_customer_notes': ('u_customer_notes', 'string'),
            'u_impacted_area': ('u_impacted_area', 'string'),
            'u_product': ('u_product', 'string'),
            'u_root_cause': ('u_root_cause', 'string'),
            'u_root_cause_subcategory': ('u_root_cause_subcategory', 'string'),
            'workaround': ('work_around', 'string'),
            'workaround_communicated_by': ('work_around_communicated_by', 'string'),
            'closed_at': ('closed_timestamp' , 'string'),
            'closed_at_timestamp': ('closed_timestamp_utc' , 'timestamp'),
            'closed_at_dt': ('closed_date' , 'date'),
            'confirmed_at': ('confirmed_timestamp' , 'string'),
            'confirmed_at_timestamp': ('confirmed_timestamp_utc' , 'timestamp'),
            'confirmed_at_dt': ('confirmed_date' , 'date'),
            'due_date': ('due_timestamp' , 'string'),
            'due_date_timestamp': ('due_timestamp_utc' , 'timestamp'),
            'due_date_dt': ('due_date' , 'date'),
            'fix_at': ('fix_timestamp' , 'string'),
            'fix_at_timestamp': ('fix_timestamp_utc' , 'timestamp'),
            'fix_at_dt': ('fix_date' , 'date'),
            'fix_communicated_at': ('fix_communicated_timestamp' , 'string'),
            'fix_communicated_at_timestamp': ('fix_communicated_timestamp_utc' , 'timestamp'),
            'fix_communicated_at_dt': ('fix_communicated_date' , 'date'),
            'reopened_at': ('reopened_timestamp' , 'string'),
            'reopened_at_timestamp': ('reopened_timestamp_utc' , 'timestamp'),
            'reopened_at_dt': ('reopened_date' , 'date'),
            'resolved_at': ('resolved_timestamp' , 'string'),
            'resolved_at_timestamp': ('resolved_timestamp_utc' , 'timestamp'),
            'resolved_at_dt': ('resolved_date' , 'date'),
            'workaround_communicated_at': ('work_around_communicated_timestamp' , 'string'),
            'workaround_communicated_at_timestamp': ('work_around_communicated_timestamp_utc' , 'timestamp'),
            'workaround_communicated_at_dt': ('work_around_communicated_date' , 'date'),
            'cdc_timestamp': ('cdc_timestamp' , 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc' , 'timestamp'),
            'cdc_timestamp_dt': ('cdc_date' , 'date'),
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

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_problem_record'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_problem_record', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
