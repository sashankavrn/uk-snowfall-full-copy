from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.data_quality_rules import dq_rules
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class PreparationNewrelicDigitalGmaFoeResponse(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.pipeline_config = self.full_configs[self.datasets]
        self.dq_rule = dq_rules.get(self.datasets)
        self.file_path = "newrelic/newrelic_digital_gma_foe_response"
        self.list_of_files = self.aws_instance.get_files_in_s3_path(f"{self.raw_bucket_name}/{self.file_path}/")


    def get_data(self):
        df = self.read_data_from_s3(self.raw_bucket_name,self.file_path,'json', multiline_json = True)
        return df


    def transform_data(self, df): 
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Add a new column with the date exactly one hour before the current timestamp
        2. Add a new column with the hour (0–23) exactly one hour before the current timestamp
        3. Extract the first item from the 'facet' column
        4. Extract local restaurant number from global_restaurant_number
        5: Drop the 'global_restaurant_number' column as it's no longer needed
        6. Fill null values in specified column
        7. Remove duplicate records.
        8. Remove trailing whitespaces
        9. Perform data quality check.
        10. Add CDC columns.
        11. Add Partition Columns
        12. Change column data types in the DataFrame

        Parameters:
        - df: Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.

        """

        # Step 1: Add a new column with the date exactly one hour before the current timestamp
        df = df.withColumn("date", F.to_date(F.current_timestamp() - F.expr("INTERVAL 1 HOUR")))

        # Step 2: Add a new column with the hour (0–23) exactly one hour before the current timestamp
        df = df.withColumn("hour", F.hour(F.current_timestamp() - F.expr("INTERVAL 1 HOUR")))

        # Step 3: Extract the first item from the 'facet' column
        df = df.withColumn("global_restaurant_number", df["facet"].getItem(0))

        # Stpe 4: Extract local restaurant number from 'global_restaurant_number'
        df = self.parse_column_values(df, self.pipeline_config.get('new_column_params'))

        # Step 5: Drop the 'global_restaurant_number' column as it's no longer needed
        df = df.drop("global_restaurant_number")

        # Stpe 6: Fill null values in specified column
        df = self.replace_value(df, self.pipeline_config.get('replace_values'))

        # Step 7: Remove duplicate records
        df = self.dropping_duplicates(df)

        # Step 8: Removes trailing whitespaces
        df = self.remove_trailing_whitespace(df)

        # Step 9: Data quality check
        df = self.data_quality_check(df, self.dq_rule,self.pipeline_config.get('primary_key'), self.raw_bucket_name, self.file_path, 'json')  

        # Step 10: Add CDC columns
        df = self.adding_cdc_columns(df)

        # Step 11: Add Partiton Columns
        df = self.create_partition_date_columns(df,'date','created')

        # step 12: Change column data types in the DataFrame
        df = self.change_column_types_data_frame(df, self.pipeline_config.get('change_column_data_type'))

        return df



    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """
        # Define the S3 save path
        save_output_path = f"s3://{self.preparation_bucket_name}/{self.file_path}/"

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

        # Check if Athena table needs to be created
        if not self.aws_instance.athena_table_exists('preparation', 'newrelic_digital_gma_foe_response'):
            # Execute Athena query to create the table
            self.aws_instance.create_athena_delta_table('preparation', 'newrelic_digital_gma_foe_response', save_output_path, self.athena_output_path)
        
        # Move files to the Archive folder
        for file_name in self.list_of_files:
            self.aws_instance.move_s3_object(self.raw_bucket_name, file_name, f"archive/{file_name}")
        
        # If error detected from DQ failing then will raise
        if self.sns_trigger:
            message = "Records in the error folder that have failed DQ rules"
            self.aws_instance.send_sns_message(message)
        
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
