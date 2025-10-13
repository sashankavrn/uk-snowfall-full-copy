from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable

class ProcessedNewrelicRmpNetworkInfo(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "newrelic/newrelic_rmp_network_info"


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
            'hostname': ('host_name', 'string'),
            'average_receivebytespersecond': ('average_receive_bytes_per_second', 'double'), 
            'average_receivedroppedpersecond': ('average_receive_dropped_per_second', 'double'), 
            'average_receiveerrorspersecond': ('average_receive_errors_per_second', 'double'), 
            'average_receivepacketspersecond': ('average_receive_packets_per_second', 'double'), 
            'average_transmitbytespersecond': ('average_transmit_bytes_per_second', 'double'), 
            'average_transmitdroppedpersecond': ('average_transmit_dropped_per_second', 'double'), 
            'average_transmiterrorspersecond': ('average_transmit_errors_per_second', 'double'), 
            'average_transmitpacketspersecond': ('average_transmit_packets_per_second', 'double'), 
            'latest_hardwareaddress': ('latest_hardware_address', 'string'), 
            'latest_interfacename': ('latest_interface_name', 'string'), 
            'latest_ipv4address': ('latest_ipv4_address', 'string'), 
            'latest_ipv6address': ('latest_ipv6_address', 'string'),
            'sys_updated_timestamp_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_timestamp': ('sys_updated_timestamp', 'string'),
            'sys_updated_timestamp_dt': ('sys_updated_date', 'date'),
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

            if not self.aws_instance.athena_table_exists('processed', 'newrelic_rmp_network_info'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'newrelic_rmp_network_info', save_output_path, self.athena_output_path)
            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
