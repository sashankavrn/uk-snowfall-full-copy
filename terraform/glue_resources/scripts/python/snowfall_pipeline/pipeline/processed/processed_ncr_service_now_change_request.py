from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from pyspark.sql import functions as F


class ProcessedNcrServiceNowChangeRequest(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        self.pipeline_config = self.full_configs[self.datasets]
        self.file_path = "ncr_service_now/change_request"


    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df


    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1: Adds incident type based on restaurant number
        2: Extracts Vista dispatch number from work notes
        3: Adds 'P' prefix to priority_id to create priority label
        4. Splits datetime column
        5. Filters passed records
        6. Drops unnecessary columns
        7. Change column names and schema.

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """
        
        df = df.withColumn("u_account", F.explode_outer(F.split("u_account", ",\s*")))

        # # Stpe 1: Extract restaurant number from account_name
        df = self.parse_column_values(df, self.pipeline_config.get('new_column_params'))

        # # Stpe 2: Fill null values in specified column
        df = self.replace_value(df, self.pipeline_config.get('replace_values'))

        # Step 1: Adds incident type based on restaurant number
        #df = df.withColumn("incident_type", F.when(F.col("restaurant_id") != -1, "Store").otherwise("Corporate"))


  
        # Step 4: Splits datetime column
        #df = self.split_datetime_column(df,self.pipeline_config.get('process_timestamp'))

        # Step 5: Filters passed records
        df = self.filter_quality_result(df,partition_column_drop=['sys_created_year','sys_created_month'])

        # Step 6: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

        #column_mapping = { }

        # Step 7. Changes column names and schema
        #df = self.change_column_names_and_schema(df, column_mapping)

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
                .partitionBy('sys_created_year','sys_created_month') \
                .save(save_output_path)
                
            else:
                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', 'ncr_service_now_change_request'):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', 'ncr_service_now_change_request', save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
