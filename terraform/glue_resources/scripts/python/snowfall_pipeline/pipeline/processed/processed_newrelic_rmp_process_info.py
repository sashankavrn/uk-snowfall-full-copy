from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from datetime import datetime, time


class ProcessedNewrelicRmpProcessInfo(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "newrelic/newrelic_rmp_process_info"


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
            'restaurant_number': ('restaurant_number', 'Integer'),
            'device': ('device', 'string'),
            'device_type': ('device_type', 'string'),
            'hostname': ('host_name', 'string'),
            'name': ('service_name', 'string'),
            'new_relic_timestamp_latest_timestamp': ('new_relic_timestamp_latest_utc', 'timestamp'),
            'new_relic_timestamp_latest': ('new_relic_timestamp_latest', 'string'),
            'new_relic_timestamp_latest_dt': ('new_relic_latest_date', 'date'),
            'api_exe_timestamp_timestamp': ('api_exe_timestamp_utc', 'timestamp'),
            'api_exe_timestamp': ('api_exe_timestamp', 'string'),
            'api_exe_timestamp_dt': ('api_exe_date', 'date'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date')
        }

        # Step 4. Changes column names and schema
        df = self.change_column_names_and_schema(df,column_mapping)

        return df



    def save_data(self, df):
            """
            Save DataFrame to an S3 location and create/update a Delta table if needed.

            Parameters:
            - df (DataFrame): Input DataFrame to be saved.

            """

            retention_days = self.pipeline_config.get('retention_days')

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

            if not self.aws_instance.athena_table_exists('processed', 'newrelic_rmp_process_info'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'newrelic_rmp_process_info', save_output_path, self.athena_output_path)

            # Get current time
            now = datetime.now().time()

            # Define your daily time window
            start_time = time(23, 55)
            end_time = time(0, 15)

            # Run only if within the time window
            if start_time <= now <= end_time:
                if isinstance(retention_days, int) and retention_days > 0:
                    s3_paths = [
                        f"s3://{self.preparation_bucket_name}/newrelic/newrelic_rmp_device_metrics/",
                        f"s3://{self.processed_bucket_name}/newrelic/newrelic_rmp_device_metrics/"
                    ]

                    for s3_path in s3_paths:
                        delta_table = DeltaTable.forPath(self.spark, s3_path)
                        
                        delta_table.delete(F.col("sys_updated_timestamp") < F.current_timestamp() - F.expr(f"INTERVAL {retention_days} DAYS"))
                        
                        delta_table.vacuum(retentionHours=48)
                    self.logger.info(f"Retention cleanup completed successfully at {datetime.now()}")
                else:
                    self.logger.info(f"Invalid retention days: {retention_days}. It must be an integer greater than 0.")
            else:
                self.logger.info("Outside the allowed time window (23:55 to 00:15). Skipping cleanup.")

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
