from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable


class ProcessedNewrelicRmpDeviceMetrics(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "newrelic/newrelic_rmp_device_metrics"


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
        4. Selecting columns to take to processed layer
        5. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """


        # Step 2: Splits datetime column
        df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 3: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['created_year','created_month'])

        # Step 4: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        # Step 5: Selecting Columns that I want to take to processed layer
        df = df.select(
            'restaurant_number',
            'device',
            'hostname',
            'latest_coreCount',
            'latest_processorCount',
            'latest_systemMemoryBytes',
            'average_cpuIOWaitPercent',
            'average_cpuIdlePercent',
            'average_cpuPercent',
            'average_cpuStealPercent',
            'average_cpuSystemPercent',
            'average_cpuUserPercent',
            'average_diskFreeBytes',
            'average_diskFreePercent',
            'average_diskReadUtilizationPercent',
            'average_diskReadsPerSecond',
            'average_diskTotalBytes',
            'average_diskUsedBytes',
            'average_diskUsedPercent',
            'average_diskUtilizationPercent',
            'average_diskWriteUtilizationPercent',
            'average_diskWritesPerSecond',
            'average_loadAverageFifteenMinute',
            'average_loadAverageFiveMinute',
            'average_loadAverageOneMinute',
            'average_memoryCachedBytes',
            'average_memoryFreeBytes',
            'average_memoryFreePercent',
            'average_memorySharedBytes',
            'average_memorySlabBytes',
            'average_memoryTotalBytes',
            'average_memoryUsedBytes',
            'average_memoryUsedPercent',
            'average_swapFreeBytes',
            'average_swapTotalBytes',
            'average_swapUsedBytes',
            'sys_updated_timestamp_timestamp',
            'sys_updated_timestamp_dt',
            'cdc_timestamp',
            'sys_updated_year',
            'sys_updated_month'
        )

        column_mapping = {
            'restaurant_number': ('restaurant_number', 'Integer'),
            'device': ('device', 'string'),
            'hostname': ('host_name', 'string'),
            'latest_coreCount': ('core_count', 'Integer'),
            'latest_processorCount': ('processor_count', 'Integer'),
            'latest_systemMemoryBytes': ('system_memory_bytes', 'double'),
            'average_cpuIOWaitPercent': ('cpu_io_wait_percent', 'double'),
            'average_cpuIdlePercent': ('cpu_idle_percent', 'double'),
            'average_cpuPercent': ('cpu_percent', 'double'),
            'average_cpuStealPercent': ('cpu_steal_percent', 'double'),
            'average_cpuSystemPercent': ('cpu_system_percent', 'double'),
            'average_cpuUserPercent': ('cpu_user_percent', 'double'),
            'average_diskFreeBytes': ('disk_free_bytes', 'double'),
            'average_diskFreePercent': ('disk_free_percent', 'double'),
            'average_diskReadUtilizationPercent': ('disk_read_utilization_percent', 'double'),
            'average_diskReadsPerSecond': ('disk_reads_per_second', 'double'),
            'average_diskTotalBytes': ('disk_total_bytes', 'double'),
            'average_diskUsedBytes': ('disk_used_bytes', 'double'),
            'average_diskUsedPercent': ('disk_used_percent', 'double'),
            'average_diskUtilizationPercent': ('disk_utilization_percent', 'double'),
            'average_diskWriteUtilizationPercent': ('disk_write_utilization_percent', 'double'),
            'average_diskWritesPerSecond': ('disk_writes_per_second', 'double'),
            'average_loadAverageFifteenMinute': ('load_average_fifteen_minute', 'double'),
            'average_loadAverageFiveMinute': ('load_average_five_minute', 'double'),
            'average_loadAverageOneMinute': ('load_average_one_minute', 'double'),
            'average_memoryCachedBytes': ('memory_cached_bytes', 'double'),
            'average_memoryFreeBytes': ('memory_free_bytes', 'double'),
            'average_memoryFreePercent': ('memory_free_percent', 'double'),
            'average_memorySharedBytes': ('memory_shared_bytes', 'double'),
            'average_memorySlabBytes': ('memory_slab_bytes', 'double'),
            'average_memoryTotalBytes': ('memory_total_bytes', 'double'),
            'average_memoryUsedBytes': ('memory_used_bytes', 'double'),
            'average_memoryUsedPercent': ('memory_used_percent', 'double'),
            'average_swapFreeBytes': ('swap_free_bytes', 'double'),
            'average_swapTotalBytes': ('swap_total_bytes', 'double'),
            'average_swapUsedBytes': ('swap_used_bytes', 'double'),
            'sys_updated_timestamp_timestamp': ('sys_updated_timestamp', 'timestamp'),
            'sys_updated_timestamp_dt': ('sys_updated_date', 'date'),
            'cdc_timestamp': ('cdc_timestamp', 'timestamp'),
            'sys_updated_year': ('sys_updated_year', 'Integer'),
            'sys_updated_month': ('sys_updated_month', 'Integer')
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
                execution_query_id = self.aws_instance.create_athena_delta_table('processed', 'newrelic_rmp_device_metrics', save_output_path, self.athena_output_path)
                
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
