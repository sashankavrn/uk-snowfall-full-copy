from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.data_quality_rules import dq_rules
from delta.tables import DeltaTable
from pyspark.sql import functions as F, types as T
import boto3
import re


class PreparationSmartsheetWorkerJob(TransformBase):
    def __init__(self, spark, sc, glueContext, dataset=None, sub_dataset=None, extension=None):
        super().__init__(spark, sc, glueContext, dataset, 'preparation')
        self.spark.conf.set("spark.sql.shuffle.partitions", "1") 
        self.spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
        self.spark.conf.set('spark.sql.caseSensitive', True)
        self.extension = extension
        self.sub_dataset = sub_dataset
        self.file_path = f"smartsheet/{sub_dataset}"
        self.list_of_files = self.aws_instance.get_files_in_s3_path(f"{self.raw_bucket_name}/{self.file_path}")

    def get_data(self):
        df = self.read_data_from_s3(self.raw_bucket_name,self.file_path,'json')
        return df

    def transform_data(self, df): 
        """
        Transform the given DataFrame.

        This method executes the following steps.
        1. Explode the nested `data` array into individual rows.
        2. Flatten the exploded `data` struct into top-level columns.
        3. Clean and standardize column names.
        4. Remove duplicate records.
        5. Remove trailing whitespaces
        6. Add CDC columns.

        Parameters:
        - df: Input DataFrame.

        Returns:
        - DataFrame: Transformed DataFrame.

        """

        # Step 1: Explode the nested `data` array into individual rows
        df = df.select(
            F.col("sheet_id"),
            F.col("sheet_name"),
            F.col("extracted_at"),
            F.explode(F.col("data")).alias("data")
        )

        # Step 2: Flatten the exploded `data` struct into top-level columns
        df = df.select(
            "sheet_id",
            "sheet_name",
            "extracted_at",
            F.col("data.*")
        )

        # Step 3: Clean and standardize column names.
        df = df.select([
            F.col(f"`{c}`").alias(self.clean_column(c))
            for c in df.columns
        ])

        # Step 4: Remove duplicate records
        df = self.dropping_duplicates(df)

        # Step 5: Removes trailing whitespaces
        df = self.remove_trailing_whitespace(df)

        # Step 6: Add CDC columns
        df = self.adding_cdc_columns(df)

        return df

    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """

        # Get the single sheet name
        sheet = df.select("sheet_name").first()["sheet_name"]

        # Replace spaces with underscores (and normalize if needed)
        table_name = "smartsheet_" + sheet.replace(" ", "_").lower()

        # Define the S3 save path
        save_output_path = f"s3://{self.preparation_bucket_name}/{self.file_path}/"

        # Write Delta table
        df.write.format("delta").mode("overwrite").save(save_output_path)

        # Vacuum
        self.vacuum_table(save_output_path, 48)

        # Create Athena table if not exists
        if not self.aws_instance.athena_table_exists('preparation', table_name):
            self.aws_instance.create_athena_delta_table(
                'preparation',
                table_name,
                save_output_path,
                self.athena_output_path
            )

        # Move files to the Archive folder
        for file_name in self.list_of_files:
            self.aws_instance.move_s3_object(self.raw_bucket_name, file_name, f"archive/{file_name}")

        # SNS alert if DQ failed
        if self.sns_trigger:
            message = "Records in the error folder that have failed DQ rules"
            self.aws_instance.send_sns_message(message)

        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')

    def clean_column(self, name):
        name = re.sub(r'[^a-zA-Z0-9]', '_', name)  # replace special chars
        name = re.sub(r'_+', '_', name)            # remove duplicates _
        return name.strip('_').lower()