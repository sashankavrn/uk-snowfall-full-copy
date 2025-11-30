from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from datetime import datetime

class ProcessedStoreDbConfig(TransformBase):

    def __init__(self, spark, sc, glueContext, dataset=None, sub_dataset=None, extension=None):
        super().__init__(spark, sc, glueContext, dataset, 'processed')
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        #self.pipeline_config = self.full_configs[self.datasets]
        self.extension = extension
        self.sub_dataset = sub_dataset
        self.file_path = f"service_agent_server_files/uploads/{sub_dataset}"

    def get_data(self):
        df = self.read_data_from_s3(self.preparation_bucket_name,self.file_path,'delta')
        return df

    def transform_data(self, df):
        """
        Transform the given DataFrame.

        This method executes the following steps:
        1. Drops unnecessary columns

        Parameters:
        - df (DataFrame): Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.
        """

        # Step 1: Drops unnecessary columns
        df = self.drop_columns_for_processed(df)

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
                .save(save_output_path)
                
            else:
                # Append the Delta table
                df.write.format("delta").mode("append") \
                .save(save_output_path)

                # Vacuum the table
                self.vacuum_table(save_output_path,48)

            if not self.aws_instance.athena_table_exists('processed', self.sub_dataset):
                # Execute Athena query to create the table
                self.aws_instance.create_athena_delta_table('processed', self.sub_dataset, save_output_path, self.athena_output_path)

            # If error detected from DQ failing then will raise
            if self.sns_trigger:
                message = "Records in the error folder that have failed transformation"
                self.aws_instance.send_sns_message(message)

            
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
