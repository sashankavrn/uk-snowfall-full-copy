from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNewrelicDigital3PoFoeResponse(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "newrelic/newrelic_digital_3po_foe_response"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Filters passed records
        2. Drops unnecessary columns
        3. Select columns to take to processed layer
        4. Standardizes vendor name from "SkipTheDishes" to "JustEat"
        5. Change column names and schema

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """

        # Step 1: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['created_year','created_month'])

        # Step 2: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        # step 3: Select columns to take to processed layer
        df = df.select(
            F.col("facet")[1].alias("foe_response"),
            F.col("facet")[2].alias("3po_response"),
            F.col("facet")[3].alias("3po_description"),
            F.col("facet")[4].alias("vendor"),
            F.col("Count").alias("count"),
            F.col("date").alias("date"),
            F.col("hour").alias("hour"),
            F.col("cdc_timestamp").alias("cdc_timestamp"),
            F.col("restaurant_number").alias("restaurant_number"),
            F.col("created_year").alias("created_year"),
            F.col("created_month").alias("created_month")
        )

        # Step 4: Standardizes vendor name from "SkipTheDishes" to "JustEat"
        df = df.withColumn(
            "vendor",
            F.when(F.col("vendor") == "SkipTheDishes", "JustEat").otherwise(F.col("vendor"))
        )

        column_mapping = {
            'restaurant_number': ('restaurant_number', 'Integer'),
            'foe_response': ('foe_response', 'Integer'),
            '3po_response': ('3po_response', 'Integer'),
            '3po_description': ('3po_description', 'string'),
            'vendor': ('vendor', 'string'),
            'count': ('count', 'Integer'),
            'date': ('date', 'date'),
            'hour': ('hour', 'integer'),
            'created_year': ('created_year', 'integer'),
            'created_month': ('created_month', 'integer'),
            'cdc_timestamp': ('cdc_timestamp', 'timestamp')
        }

        # Step 5. Change column names and schema
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
                .partitionBy('created_year','created_month') \
                .save(save_output_path)
                
            else:

                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', 'newrelic_digital_3po_foe_response'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'newrelic_digital_3po_foe_response', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
