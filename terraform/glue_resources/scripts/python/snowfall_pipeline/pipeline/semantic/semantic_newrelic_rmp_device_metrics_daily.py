from snowfall_pipeline.common_utilities.transform_base import TransformBase
from datetime import datetime, timedelta
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import boto3
from snowfall_pipeline.common_utilities.aws_utilities import AwsUtilities


class SemanticNewrelicRmpDeviceMetricsDaily(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5")
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "newrelic/newrelic_rmp_device_metrics"

    def get_data(self):

        df = self.spark.read.format("delta").load(f"s3://{self.processed_bucket_name}/{self.file_path}/")

        return df

    def transform_data(self, df):

        self.logger.info("Transforming data")
        # Filter the data to include only records from the last 1 day based on sys_updated_timestamp
        df = df.filter(F.col('sys_updated_timestamp') >= F.current_timestamp() - F.expr('INTERVAL 1 DAY'))

        # Define the window specification for getting the latest records
        window_spec = Window.partitionBy('restaurant_number', 'device', 'host_name').orderBy(F.col('sys_updated_timestamp').desc())

        # Get the latest records for core_count, processor_count and system_memory_bytes
        df_staging1 = df.withColumn('rank', F.row_number().over(window_spec)) \
            .filter(F.col('rank') == 1) \
            .select(
                'restaurant_number',
                'device',
                'host_name',
                'latest_core_count',
                'latest_processor_count',
                'latest_system_memory_bytes'
            )

        self.logger.info("Latest records extracted")
        
        # Calculate the average for the rest of the columns
        df_staging2 = df.groupBy('restaurant_number', 'device', 'host_name').agg(
            F.avg('average_cpu_io_wait_percent').alias('average_cpu_io_wait_percent'),
            F.avg('average_cpu_idle_percent').alias('average_cpu_idle_percent'),
            F.avg('average_cpu_percent').alias('average_cpu_percent'),
            F.avg('average_cpu_steal_percent').alias('average_cpu_steal_percent'),
            F.avg('average_cpu_system_percent').alias('average_cpu_system_percent'),
            F.avg('average_cpu_user_percent').alias('average_cpu_user_percent'),
            F.avg('average_disk_free_bytes').alias('average_disk_free_bytes'),
            F.avg('average_disk_free_percent').alias('average_disk_free_percent'),
            F.avg('average_disk_read_utilization_percent').alias('average_disk_read_utilization_percent'),
            F.avg('average_disk_reads_per_second').alias('average_disk_reads_per_second'),
            F.avg('average_disk_total_bytes').alias('average_disk_total_bytes'),
            F.avg('average_disk_used_bytes').alias('average_disk_used_bytes'),
            F.avg('average_disk_used_percent').alias('average_disk_used_percent'),
            F.avg('average_disk_utilization_percent').alias('average_disk_utilization_percent'),
            F.avg('average_disk_write_utilization_percent').alias('average_disk_write_utilization_percent'),
            F.avg('average_disk_writes_per_second').alias('average_disk_writes_per_second'),
            F.avg('average_load_average_fifteen_minute').alias('average_load_average_fifteen_minute'),
            F.avg('average_load_average_five_minute').alias('average_load_average_five_minute'),
            F.avg('average_load_average_one_minute').alias('average_load_average_one_minute'),
            F.avg('average_memory_cached_bytes').alias('average_memory_cached_bytes'),
            F.avg('average_memory_free_bytes').alias('average_memory_free_bytes'),
            F.avg('average_memory_free_percent').alias('average_memory_free_percent'),
            F.avg('average_memory_shared_bytes').alias('average_memory_shared_bytes'),
            F.avg('average_memory_slab_bytes').alias('average_memory_slab_bytes'),
            F.avg('average_memory_total_bytes').alias('average_memory_total_bytes'),
            F.avg('average_memory_used_bytes').alias('average_memory_used_bytes'),
            F.avg('average_memory_used_percent').alias('average_memory_used_percent'),
            F.avg('average_swap_free_bytes').alias('average_swap_free_bytes'),
            F.avg('average_swap_total_bytes').alias('average_swap_total_bytes'),
            F.avg('average_swap_used_bytes').alias('average_swap_used_bytes'),
            F.current_timestamp().alias('sys_updated_timestamp'),
            F.current_date().alias('sys_updated_date'),
            F.year(F.current_date()).alias('sys_updated_year'),
            F.month(F.current_date()).alias('sys_updated_month')
        )

        self.logger.info("Aggregated metrics computed")

        # Join the latest records with the aggregated averages
        df = df_staging1.join(df_staging2, on=['restaurant_number', 'device', 'host_name'], how='inner')

        return df



    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """
        retention_days = self.pipeline_config.get('retention_days')

        # Define the S3 save path
        save_output_path = f"s3://{self.semantic_bucket_name}/newrelic/newrelic_rmp_device_metrics/"


        # Check if Delta table needs to be created
        if DeltaTable.isDeltaTable(self.spark, save_output_path) is False:
            self.athena_trigger = True

        # Determine whether to create or merge to the Delta table
        if self.athena_trigger:
            # Create the Delta table
            df.write.format("delta").mode("overwrite") \
                .partitionBy('sys_updated_year','sys_updated_month') \
                .save(save_output_path)

            # Execute Athena query to create the table
            execution_query_id = self.aws_instance.create_athena_delta_table('semantic',
                                                                             'newrelic_rmp_device_metrics',
                                                                             save_output_path,
                                                                             self.athena_output_path)

        else:

            # Append the new DataFrame to the Delta table
            df.write.format("delta").mode("append") \
                .save(save_output_path)
            
        if isinstance(retention_days, int) and retention_days > 0:

            s3_paths = [
                f"s3://{self.preparation_bucket_name}/newrelic/newrelic_rmp_device_metrics/",
                f"s3://{self.processed_bucket_name}/newrelic/newrelic_rmp_device_metrics/"
            ]

            for s3_path in s3_paths:
                delta_table = DeltaTable.forPath(self.spark, s3_path)
                
                delta_table.delete(F.col("sys_updated_timestamp") < F.current_timestamp() - F.expr(f"INTERVAL {retention_days} DAYS"))
                
                delta_table.vacuum(retentionHours=48)
        else:
            self.logger.info(f"Invalid retention days: {retention_days}. It must be an integer greater than 0.")
        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
        