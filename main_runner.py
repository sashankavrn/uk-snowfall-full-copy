import importlib
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
  
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)


def snake_to_camel(snake_str):
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)



def run_workflow(variable):
    parts = variable.split('_')
    if parts[0] == "preparation":
        module_prefix = parts[0]
        class_name = snake_to_camel(variable)
        prep_module_path = f"pipeline.{module_prefix}.{variable}" 
        try:
            prep_module = importlib.import_module(prep_module_path)
            prep_class = getattr(prep_module,class_name)
            prep_instance = prep_class(spark,sc,glueContext)
            prep_instance.process_flow()
        except Exception as e:
            print(e)
            print("Preparation module not found for variable value:", variable)
        
        processed_variable = f"processed_{parts[1]}_{parts[2]}"
        class_name = snake_to_camel(processed_variable)
        processed_module_path = f"pipeline.processed.{processed_variable}"

        try:
            processed_module = importlib.import_module(processed_module_path)
            processed_class = getattr(processed_module,class_name)
            processed_instance = processed_class(spark,sc,glueContext)
            processed_instance.process_flow()
        except Exception as e:
            print(e)
            print("Processed module not found for variable value:", processed_variable)

    else:
        module_prefix = parts[0] 
        class_name = snake_to_camel(variable)
        module_path = f"pipeline.{module_prefix}.{variable}"
        try:
            module = importlib.import_module(module_path)
            my_class = getattr(module, class_name)
            my_instance = my_class(spark,sc,glueContext)
            my_instance.process_flow()

        except Exception as e:
            print(e)
            print("Module not found for variable value:", variable)




variable = "processed_incident_intraday"
run_workflow(variable)
