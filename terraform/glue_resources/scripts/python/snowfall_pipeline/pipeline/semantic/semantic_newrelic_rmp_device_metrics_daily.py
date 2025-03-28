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
        self.retention_days = self.aws_instance.get_workflow_properties('RETENTION_DAYS')
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
                'lates_core_count',
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

        ## Convert retention_days to integer      
        try:
            self.retention_days = int(self.retention_days)
        except (ValueError, TypeError):
            self.logger.warning(f"Invalid retention_days ({self.retention_days}). Setting to default 60.")
            self.retention_days = 60

        # Ensure retention_days is positive
        if self.retention_days <= 0:
            self.logger.warning(f"Invalid retention_days ({self.retention_days}). Setting to default 60.")
            self.retention_days = 60


        # Define the S3 save path
        save_output_path = f"s3://{self.semantic_bucket_name}/newrelic/newrelic_rmp_device_metrics/"
        prepare_s3_path = f"s3://{self.preparation_bucket_name}/newrelic/newrelic_rmp_device_metrics/"
        process_s3_path = f"s3://{self.processed_bucket_name}/newrelic/newrelic_rmp_device_metrics/"

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
            

        # Load the Delta table as a DeltaTable
        delta_table_prepare = DeltaTable.forPath(self.spark, prepare_s3_path)
        delta_table_process = DeltaTable.forPath(self.spark, process_s3_path)

        # Delete records where sys_updated_date is older than {self.retention_days} days.
        delta_table_prepare.delete(F.col("sys_updated_timestamp") < F.current_timestamp() - F.expr(f"INTERVAL {self.retention_days} DAYS"))
        delta_table_prepare.vacuum(retentionHours=48)

        delta_table_process.delete(F.col("sys_updated_timestamp") < F.current_timestamp() - F.expr(f"INTERVAL {self.retention_days} DAYS"))
        delta_table_process.vacuum(retentionHours=48)
        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
        