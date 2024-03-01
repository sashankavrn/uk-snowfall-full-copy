from common_utilities.transform_base import TransformBase


class ProcessedIncidentIntraday(TransformBase):


    def load_data(self):
        "Abstract method which will be overridden when this class is inherited"
        pass

    def transform_data(self):
        "Abstract method which will be overridden when this class is inherited"
        pass

    def export_data(self):
        "Abstract method which will be overridden when this class is inherited"
        pass

    def process_flow(self):
        print('Running process flow method which is for the processed class')
        return