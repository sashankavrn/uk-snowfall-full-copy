from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable

class ProcessedGenesysSessionSummary(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "genesys/session_summary"

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
        df = self.filter_quality_result(df)

        # Step 3: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'conversationid': ('conversation_id', 'string'),
            'conversationstarttime_timestamp': ('conversation_start_time_utc', 'timestamp'),
            'conversationstarttime': ('conversation_start_time', 'string'),
            'conversationstarttime_dt': ('conversation_start_date', 'date'),
            'conversationendtime_timestamp': ('conversation_end_time_utc', 'timestamp'),
            'conversationendtime': ('conversation_end_time', 'string'),
            'conversationendtime_dt': ('conversation_end_date', 'date'),
            'sessionid': ('session_id', 'string'),
            'sessionstarttime_timestamp': ('session_start_time_utc', 'timestamp'),
            'sessionstarttime': ('session_start_time', 'string'),
            'sessionstarttime_dt': ('session_start_date', 'date'),
            'sessionendtime_timestamp': ('session_end_time_utc', 'timestamp'),
            'sessionendtime': ('session_end_time', 'string'),
            'sessionendtime_dt': ('session_end_date', 'date'),
            'sessionindex': ('session_index', 'integer'),
            'sessioncount': ('session_count', 'integer'),
            'sessionduration': ('session_duration', 'long'),
            'purpose': ('purpose', 'string'),
            'peerid': ('peer_id', 'string'),
            'participantid': ('participant_id', 'string'),
            'participantname': ('participant_name', 'string'),
            'userid': ('user_id', 'string'),
            'username': ('user_name', 'string'),
            'userhandled': ('user_handled', 'integer'),
            'queueid': ('queue_id', 'string'),
            'queuename': ('queue_name', 'string'),
            'direction': ('direction', 'string'),
            'originatingdirection': ('originating_direction', 'string'),
            'abandoned': ('abandoned', 'integer'),
            'queueanswered': ('queue_answered', 'integer'),
            'agentanswered': ('agent_answered', 'integer'),
            'totalagentwrapupduration': ('total_agent_wrapup_duration', 'long'),
            'totalagenttalkduration': ('total_agent_talk_duration', 'long'),
            'totalacdwaitduration': ('total_acd_wait_duration', 'long'),
            'totalagentalertduration': ('total_agent_alert_duration', 'long'),
            'totalcontactingduration': ('total_contacting_duration', 'long'),
            'totaldialingduration': ('total_dialing_duration', 'long'),
            'offered': ('offered', 'integer'),
            'transferto': ('transfer_to', 'string'),
            'transfertoid': ('transfer_to_id', 'string'),
            'transfertopurpose': ('transfer_to_purpose', 'string'),
            'wrapupcode': ('wrapup_code', 'string'),
            'wrapupcodename': ('wrapup_code_name', 'string'),
            'env_tag_name': ('env_tag_name', 'string'),
            'externaltag': ('external_tag', 'string'),
            'transaction_company_owner_name': ('transaction_company_owner_name', 'string'),
            'ani': ('ani', 'string'),
            'dnis': ('dnis', 'string'),
            'originatingdnis': ('originating_dnis', 'string'),
            'disconnecttype': ('disconnect_type', 'string'),
            'mediatype': ('media_type', 'string'),
            'messagetype': ('message_type', 'string'),
            'addressfrom': ('address_from', 'string'), 
            'addressto': ('address_to', 'string'), 
            'totalagentholdduration': ('total_agent_hold_duration', 'long'), 
            'holdcount': ('hold_count', 'long'), 
            'consulttransferred': ('consult_transferred', 'long'), 
            'consultcount': ('consult_count', 'long'), 
            'flowout': ('flow_out', 'long'), 
            'alertnoanswer': ('alert_no_answer', 'long'), 
            'blindtransferred': ('blind_transferred', 'long'), 
            'transferred': ('transferred', 'long'), 
            'errors': ('errors', 'long'), 
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date')
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
                .save(save_output_path)
                
            else:
                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', 'genesys_session_summary'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'genesys_session_summary', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')


