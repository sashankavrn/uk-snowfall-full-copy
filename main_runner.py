import importlib
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
  
class RunManager:

    def __init__(self, spark_context):
        # Initialise logging
        self.logger = logging.getLogger(__name__)
        self.glueContext = GlueContext(spark_context) #TODO WHY ARE THESE MADE BUT NEVER USED
        self.spark = glueContext.spark_session
        self.job = Job(glueContext)

    def run(group, dataset):
        #TODO ANY PRIOR STEPS BEFORE WE PROCESS
        run_grouping = getattr(sys.modules[__name__], f'run_{group}')
        run_grouping(dataset)

    def run_preperation(dataset): #TODO THIS IS WHERE OBSCURE EXCEPTIONS AND OUR RESOLUTION SHOULD TAKE PLACE, THEN CONTINURE OR END
        pipeline_instance = __fetch_pipeline_class__(group='preperation', dataset=dataset)
        pipeline_instance.process_flow()
        run_processed(dataset) # Run processed after preperation

    def run_processed(dataset):
        pipeline_instance = __fetch_pipeline_class__(group='processed', dataset=dataset)
        pipeline_instance.process_flow()

    def run_semantic(dataset):
        pipeline_instance = __fetch_pipeline_class__(group='semantic', dataset=dataset)
        pipeline_instance.process_flow()

    def __fetch_pipeline_class__(group, dataset):
        try:
            module = importlib.import_module(prep_module_path)
            prep_class = getattr(module, snake_to_camel(f"{group}_{dataset}"))
            return prep_class(spark,sc,glueContext)
        except AttributeError as e:
            #TODO WHATEVER NEEDS TO HAPPEN HERE
            sys.exit("Exiting the code with sys.exit() as no correct module could be found!")

    def snake_to_camel(snake_str):
        components = snake_str.split('_')
        return ''.join(x.title() for x in components)

def main():
    group = "processed" #TODO THIS WOULD BE WHERE YOU GET YOUR ENV VARS
    dataset = "incident_intraday"
    sc = SparkContext.getOrCreate()
    
    try:
        run_manager = RunManager(sc)
        run_manager.run(group=group, dataset=dataset)
    except Exception as e: #TODO ULTIMATE EXCEPTION CATCH FOR ANYTHING OUTSIDE OF PROCESSING
        logger.critical(f"Unhandled exception occurred. Attempting to shut down spark context. Error details:")
        logger.exception(e)
    finally:
        sparkContext.stop()
        spark.stop()

if __name__ == "__main__":
    main()
