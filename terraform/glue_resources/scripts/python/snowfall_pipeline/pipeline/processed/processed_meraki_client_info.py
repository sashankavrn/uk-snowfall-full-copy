from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql.functions import col


class ProcessedMerakiClientInfo(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "meraki/client_info"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Flatten nested 'usage' fields into individual columns
        2. Splits datetime column
        3. Filters passed records
        4. Drops unnecessary columns
        5. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
        # Step 1: Flatten nested 'usage' fields into individual columns, then drop the original 'usage' struct
        df = df \
            .withColumn("usage_recv", col("usage.recv")) \
            .withColumn("usage_sent", col("usage.sent")) \
            .withColumn("usage_total", col("usage.total")) \
            .drop("usage")

        # Step 2: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 3: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_updated_year','sys_updated_month'])

        # Step 4: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        column_mapping = {
            'restaurant_number': ('restaurant_number', 'Integer'),
            'description': ('description', 'string'),
            'devicetypeprediction': ('device_type_prediction', 'string'),
            'firstseen': ('first_seen', 'string'),
            'id': ('id', 'string'),
            'ip': ('ip', 'string'),
            'ip6': ('ip6', 'string'),
            'ip6local': ('ip6_local', 'string'),
            'lastseen': ('last_seen', 'string'),
            'mac': ('mac_address', 'string'),
            'manufacturer': ('manufacturer', 'string'),
            'networkname': ('network_name', 'string'),
            'os': ('os', 'string'),
            'recentdeviceconnection': ('recent_device_connection', 'string'),
            'recentdevicemac': ('recent_device_mac', 'string'),
            'recentdevicename': ('recent_device_name', 'string'),
            'recentdeviceserial': ('recent_device_serial', 'string'),
            'ssid': ('ssid', 'string'),
            'status': ('status', 'string'),
            'switchport': ('switch_port', 'string'),
            'usage_recv': ('usage_recv', 'long'),
            'usage_sent': ('usage_sent', 'long'),
            'usage_total': ('usage_total', 'long'),
            'vlan': ('vlan', 'string'),
            'wirelesscapabilities': ('wireless_capabilities', 'string'), 
            'sys_updated_timestamp_timestamp': ('sys_updated_timestamp_utc', 'timestamp'),
            'sys_updated_timestamp': ('sys_updated_timestamp', 'string'),
            'sys_updated_timestamp_dt': ('sys_updated_date', 'date'),
            'cdc_timestamp_timestamp': ('cdc_timestamp_utc', 'timestamp'),
            'cdc_timestamp': ('cdc_timestamp', 'string'),
            'cdc_timestamp_dt': ('cdc_date', 'date'),
            'sys_updated_year': ('sys_updated_year', 'integer'), 
            'sys_updated_month': ('sys_updated_month', 'integer')
        }

        # Step 5. Changes column names and schema
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
                .partitionBy('sys_updated_year','sys_updated_month') \
                .save(save_output_path)
                
            else:

                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', 'meraki_client_info'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'meraki_client_info', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
