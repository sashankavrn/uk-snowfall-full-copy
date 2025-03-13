from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable


class ProcessedMeraki(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "meraki"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Explode and pivot JSON column
        2. Splits datetime column
        3. Filters passed records
        4. Drops unnecessary columns
        5. Selecting columns to take to processed layer
        6. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """

        # Step 1: Explode and pivot JSON column
        df = self.explode_pivot_json_column(df, self.pipeline_config.get('transform_json'))

        # Step 2: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))


        # Step 3: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['created_year','created_month'])

        # Step 4: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        # Step 5: Selecting Columns that I want to take to processed layer
        df = df.select(
            'restaurant_number',
            'name',
            'serial',
            'mac',
            'networkId',
            'productType',
            'model',
            'address',
            'lat',
            'lng',
            'notes',
            'tags',
            'wan1Ip',
            'wan2Ip',
            'configurationUpdatedAt',
            'firmware',
            'url',
            'Monitoring version',
            'Running software version',
            'sys_updated_year',
            'sys_updated_month',
            'sys_updated_timestamp_timestamp',
            'sys_updated_timestamp_dt'
        )

        column_mapping = {
            'restaurant_number': ('restaurant_number', 'Integer'),
            'name': ('device_name', 'string'),
            'serial': ('serial_number', 'string'),
            'mac': ('mac_address', 'string'),
            'networkId': ('network_id', 'string'),
            'productType': ('product_type', 'string'),
            'model': ('model', 'string'),
            'address': ('address', 'string'),
            'lat': ('latitude', 'double'),
            'lng': ('longitude', 'double'),
            'notes': ('notes', 'string'),
            'tags': ('tags', 'string'),
            'wan1Ip': ('wan1_ip', 'string'),
            'wan2Ip': ('wan2_ip', 'string'),
            'configurationUpdatedAt': ('config_updated_at', 'string'),
            'firmware': ('firmware_version', 'string'),
            'url': ('device_url', 'string'),
            'Monitoring version': ('monitoring_version', 'string'),
            'Running software version': ('running_software_version', 'string'),
            'sys_updated_year': ('sys_updated_year', 'Integer'),
            'sys_updated_month': ('sys_updated_month', 'Integer'),
            'sys_updated_timestamp_timestamp': ('sys_updated_timestamp', 'string'),
            'sys_updated_timestamp_dt': ('sys_updated_date', 'date')
        }
        # Step 6. Changes column names and schema
        df = self.change_column_names_and_schema(df,column_mapping)

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
                .partitionBy('sys_updated_year','sys_updated_month') \
                .save(save_output_path)

                # Execute Athena query to create the table
                execution_query_id = self.aws_instance.create_athena_delta_table('processed', 'meraki_devices_info', save_output_path, self.athena_output_path)

                # Change string data type to timestamp via glue schema
                if self.aws_instance.check_query_status(execution_query_id) is True:
                    timestamp_columns = [
                    'sys_updated_timestamp'
                    ]
           
                    self.aws_instance.update_table_columns_to_timestamp('processed','meraki_devices_info',timestamp_columns)
                
            else:

                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)


            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
