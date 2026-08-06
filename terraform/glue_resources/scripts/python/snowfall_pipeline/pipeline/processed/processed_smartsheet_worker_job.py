from snowfall_pipeline.common_utilities.transform_base import TransformBase
from snowfall_pipeline.common_utilities.decorators import transformation_timer
from delta.tables import DeltaTable
from datetime import datetime

class ProcessedSmartsheetWorkerJob(TransformBase):

    def __init__(self, spark, sc, glueContext, dataset=None, sub_dataset=None, extension=None):
        super().__init__(spark, sc, glueContext, dataset, 'processed')
        self.spark.conf.set("spark.sql.shuffle.partitions", "5") 
        #self.pipeline_config = self.full_configs[self.datasets]
        self.extension = extension
        self.sub_dataset = sub_dataset
        self.file_path = f"service_agent_server_files/uploads/{sub_dataset}"

    def get_data(self):
        return None

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

        return None


    def save_data(self, df):
            """
            Save DataFrame to an S3 location and create/update a Delta table if needed.

            Parameters:
            - df (DataFrame): Input DataFrame to be saved.

            """

            if df is None:
                self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')

