from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from datetime import datetime

class ProcessedNcrServiceNowKnowledge(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/knowledge"

    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df

    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Check if DataFrame is empty
        2. Decode HTML entities
        3. Remove HTML tags
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
        df = self.html_entity_decoder(df, self.pipeline_config.get('html_entity_columns'))

        # Step 3: Remove HTML tags from specified string columns
        df = self.strip_html_tags (df, self.pipeline_config.get('html_tag_columns'))

        # Step 4: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 5: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 6: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'active': ('active', 'string'),
            'article_id': ('article_id', 'string'),
            'article_type_display_value': ('article_type', 'string'),
            'article_type_id': ('article_type_id', 'string'),
            'author_display_value': ('author', 'string'),
            'author_id': ('author_id', 'string'),
            'base_version_display_value': ('base_version', 'string'),
            'base_version_id': ('base_version_id', 'string'),
            'can_read_user_criteria': ('can_read_user_criteria', 'string'),
            'confidence': ('confidence', 'string'),
            'direct': ('direct', 'string'),
            'disable_commenting': ('disable_commenting', 'string'),
            'disable_suggesting': ('disable_suggesting', 'string'),
            'display_attachments': ('display_attachments', 'string'),
            'display_number': ('display_number', 'string'),
            'flagged': ('flagged', 'string'),
            'generated_with_now_assist': ('generated_with_now_assist', 'string'),
            'helpful_count': ('helpful_count', 'int'),
            'instrumentation_metadata': ('instrumentation_metadata', 'string'),
            'kb_category_display_value': ('kb_category', 'string'),
            'kb_category_id': ('kb_category_id', 'string'),
            'kb_knowledge_base_display_value': ('kb_knowledge_base', 'string'),
            'kb_knowledge_base_id': ('kb_knowledge_base_id', 'string'),
            'language_display_value': ('language', 'string'),
            'language_id': ('language_id', 'string'),
            'latest': ('latest', 'string'),
            'meta': ('meta', 'string'),
            'meta_description': ('meta_description', 'string'),
            'published': ('published', 'timestamp'),
            'rating': ('rating', 'decimal(5,2)'),
            'revised_by_display_value': ('revised_by', 'string'),
            'revised_by_id': ('revised_by_id', 'string'),
            'roles': ('roles', 'string'),
            'scheduled_publish_date': ('scheduled_publish_date', 'string'),
            'short_description': ('short_description', 'string'),
            'summary_display_value': ('summary', 'string'),
            'summary_id': ('summary_id', 'string'),
            'sys_class_name': ('sys_class_name', 'string'),
            'sys_created_by': ('sys_created_by', 'string'),
            'sys_created_on_timestamp': ('sys_created_timestamp_utc', 'timestamp'),
            'sys_created_on': ('sys_created_timestamp', 'string'),
            'sys_created_on_dt': ('sys_created_date', 'date'),
            'sys_domain': ('sys_domain', 'string'),
            'sys_domain_path': ('sys_domain_path', 'string'),
            'sys_id': ('sys_id', 'string'),
            'sys_mod_count': ('sys_mod_count', 'int'),
            'sys_updated_by': ('sys_updated_by', 'string'),
            'sys_updated_on_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_on': ('sys_updated_timestamp', 'string'),
            'sys_updated_on_dt': ('sys_updated_date', 'date'),
            'sys_view_count': ('sys_view_count', 'int'),
            'text': ('text', 'string'),
            'u_audience': ('u_audience', 'string'),
            'u_candescent_only': ('u_candescent_only', 'string'),
            'u_hr_professionals_only_article': ('u_hr_professionals_only_article', 'string'),
            'u_kb_additional_information_and_faqs': ('u_kb_additional_information_and_faqs', 'string'),
            'u_kb_troubleshooting_and_verification': ('u_kb_troubleshooting_and_verification', 'string'),
            'u_knowledge_type': ('u_knowledge_type', 'string'),
            'u_visibility': ('u_visibility', 'string'),
            'use_count': ('use_count', 'int'),
            'valid_to': ('valid_to', 'timestamp'),
            'version_display_value': ('version', 'string'),
            'version_id': ('version_id', 'string'),
            'view_as_allowed': ('view_as_allowed', 'string'),
            'workflow_state': ('workflow_state', 'string'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_timestamp_date', 'date'),
            'sys_created_year': ('sys_created_year', 'Integer'),
            'sys_created_month': ('sys_created_month', 'Integer')
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

        if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_knowledge'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_knowledge', save_output_path, self.athena_output_path)

        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed transformation"
            self.aws_instance.send_sns_message(message)

        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
