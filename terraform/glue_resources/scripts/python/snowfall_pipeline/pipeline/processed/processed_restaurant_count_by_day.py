from snowfall_pipeline.common_utilities.transform_base import TransformBase
from datetime import datetime, timedelta
from delta.tables import DeltaTable
from pyspark.sql import functions as F
from pyspark.sql.window import Window
import boto3
from snowfall_pipeline.common_utilities.aws_utilities import AwsUtilities


class ProcessedRestaurantCountByDay(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5")
        #self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "restaurant_count_by_day"

    def get_data(self):

        df = self.spark.read.format("delta").load(f"s3://{self.processed_bucket_name}/ods/location_hierarchy/")

        return df

    def transform_data(self, df):

        self.logger.info("Transforming data")

        # Filter the DataFrame for currently open stores
        df = df.filter(
            ((F.col("open_date").isNotNull()) & (F.col("open_date") <= F.current_date())) &
            ((F.col("close_date").isNull()) | (F.col("close_date") > F.current_date())) &
            (F.col("store_status") == "A")
        )

        # Aggregate into a single-row DataFrame with count and current date
        df = df.agg(
            F.countDistinct("store_number").alias("restaurant_count"),
            F.current_date().alias("report_date")
        )

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
        if DeltaTable.isDeltaTable(self.spark, save_output_path) is False:
            self.athena_trigger = True

        # Determine whether to create or merge to the Delta table
        if self.athena_trigger:
            # Create the Delta table
            df.write.format("delta").mode("overwrite") \
                .save(save_output_path)

        else:

            # Append the new DataFrame to the Delta table
            df.write.format("delta").mode("append") \
                .save(save_output_path)
            
        # Vacuum the table
        self.vacuum_table(save_output_path,48)
            
        if not self.aws_instance.athena_table_exists('processed', 'restaurant_count_by_day'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('processed', 'restaurant_count_by_day', save_output_path, self.athena_output_path)

        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
        