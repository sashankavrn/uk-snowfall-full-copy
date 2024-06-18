from snowfall_pipeline.common_utilities.transform_base import TransformBase
from datetime import datetime, timedelta
from delta.tables import DeltaTable
import boto3


class SemanticDailyIncidents(TransformBase):

    def __init__(self, spark, sc, glueContext):
        super().__init__(spark, sc, glueContext)
        self.spark.conf.set("spark.sql.shuffle.partitions", "5")
        self.reporting_date = self.aws_instance.get_workflow_properties('REPORTING_DATE')
        self.file_path = "service_now/incident/daily"

    def get_data(self):
        df = self.spark.read.format("delta").load(f"s3://{self.processed_bucket_name}/{self.file_path}/")
        return df

    def transform_data(self, df):

        df.createOrReplaceTempView("service_now_incident_daily")

        # Check if max_date is empty
        if self.reporting_date:
            try:
                # Parse max_date if not empty
                report_date_obj = datetime.strptime(self.reporting_date, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Invalid date format. Please provide date in 'yyyy-mm-dd' format.")
        else:
            # If max_date is empty, get yesterday's date
            report_date_obj = datetime.now() - timedelta(days=1)

        # Format max_date to 'yyyy-mm-dd' format
        self.formatted_reporting_date = report_date_obj.strftime('%Y-%m-%d')

        self.logger.info(f"Reporting date selected: {self.formatted_reporting_date}")

        sql_query = f"""
            Select 
                    restaurant_id,
                    restaurant_name,
                    restaurant_full_name,
                    incident_id,
                    incident_short_description,
                    incident_state,
                    eod_incident_status,
                    opened_at_date,
                    opened_at_timestamp,
                    resolved_at_date,
                    resolved_at_timestamp,
                    incident_priority_local,
                    incident_priority_global,
                    incident_category,
                    incident_subcategory,
                    assignment_group,
                    service_offering,
                    service_vendor,
                    reporting_date,
                    sys_updated_date,
                    closed_date,
                    sys_updated_timestamp,
                    closed_timestamp,
                    reopened_date,
                    reopened_timestamp,
                    hold_reason,
                    contact_type,
                    impact,
                    severity,
                    urgency,
                    active_flag
            From(
            SELECT *,
                RANK() OVER (PARTITION BY incident_id ORDER BY CAST(sys_updated_timestamp AS TIMESTAMP) DESC) AS rank
                FROM (
                    SELECT
                        restaurant_id,
                        restaurant_name,
                        CASE WHEN restaurant_id = -1 THEN restaurant_name 
                            ELSE CONCAT(CAST(restaurant_id AS string), ' ', restaurant_name) 
                        END AS restaurant_full_name,
                        incident_number AS incident_id,
                        short_description AS incident_short_description,
                        state AS incident_state,
                        CASE WHEN opened_date = resolved_at_date 
                            AND opened_date = date('{self.formatted_reporting_date}')
                            THEN 'New and Resolved' ELSE state 
                        END AS eod_incident_status,
                        opened_date AS opened_at_date,
                        opened_timestamp AS opened_at_timestamp,
                        resolved_at_date AS resolved_at_date,
                        resolved_at_timestamp AS resolved_at_timestamp,
                        priority AS incident_priority_local,
                        priority AS incident_priority_global,
                        category AS incident_category,
                        subcategory AS incident_subcategory,
                        assignment_group,
                        service_offering,
                        u_vendor AS service_vendor,
                        date('{self.formatted_reporting_date}')AS reporting_date,
                        sys_updated_date,
                        closed_date,
                        CASE when closed_date = date('{self.formatted_reporting_date}')
                            OR closed_date is null then 1 else 0 
                        END AS inc_close_validate,
                        sys_updated_timestamp,
                        closed_timestamp,
                        reopened_time_date AS reopened_date,
                        reopened_timestamp,
                        hold_reason,
                        contact_type,
                        impact,
                        severity,
                        urgency,
                        active_flag
                    FROM service_now_incident_daily
                    WHERE (sys_updated_date = date('{self.formatted_reporting_date}') 
                    OR opened_date = date('{self.formatted_reporting_date}'))
                                        
                    UNION
                    
                    SELECT
                        restaurant_id,
                        restaurant_name,
                        CASE WHEN restaurant_id = -1 THEN restaurant_name 
                            ELSE CONCAT(CAST(restaurant_id AS string), ' ', restaurant_name) 
                        END AS restaurant_full_name,
                        incident_number AS incident_id,
                        short_description AS incident_short_description,
                        state AS incident_state,
                        CASE WHEN opened_date = resolved_at_date 
                            AND opened_date = date('{self.formatted_reporting_date}')
                            THEN 'New and Resolved' ELSE state 
                        END AS eod_incident_status,
                        opened_date AS opened_at_date,
                        opened_timestamp AS opened_at_timestamp,
                        resolved_at_date AS resolved_at_date,
                        resolved_at_timestamp AS resolved_at_timestamp,
                        priority AS incident_priority_local,
                        priority AS incident_priority_global,
                        category AS incident_category,
                        subcategory AS incident_subcategory,
                        assignment_group,
                        service_offering,
                        u_vendor AS service_vendor,
                        date('{self.formatted_reporting_date}')AS reporting_date,
                        sys_updated_date,
                        closed_date,
                        CASE when state NOT IN ('Closed')
                            OR closed_date is null then 1 else 0 
                        END AS inc_close_validate,
                        sys_updated_timestamp,
                        closed_timestamp,
                        reopened_time_date AS reopened_date,
                        reopened_timestamp,
                        hold_reason,
                        contact_type,
                        impact,
                        severity,
                        urgency,
                        active_flag
                    FROM service_now_incident_daily
                    WHERE sys_updated_date < date('{self.formatted_reporting_date}') 
                    
                ) dataset
            )
            WHERE inc_close_validate = 1 AND rank = 1
        """
        self.logger.info(f"Running the SQL Query: {sql_query}")

        result_df = self.spark.sql(sql_query)

        return result_df

    def save_data(self, df):
        """
        Save DataFrame to an S3 location and create/update a Delta table if needed.

        Parameters:
        - df (DataFrame): Input DataFrame to be saved.

        """
        # Define the S3 save path
        save_output_path = f"s3://{self.semantic_bucket_name}/daily_incidents/"

        # Check if Delta table needs to be created
        if DeltaTable.isDeltaTable(self.spark, save_output_path) is False:
            self.athena_trigger = True

        # Determine whether to create or merge to the Delta table
        if self.athena_trigger:
            # Create the Delta table
            df.write.format("delta").mode("overwrite") \
                .partitionBy('reporting_date') \
                .save(save_output_path)

            # Execute Athena query to create the table
            execution_query_id = self.aws_instance.create_athena_delta_table('semantic',
                                                                             'view_daily_incident_pre_snapshot',
                                                                             save_output_path,
                                                                             self.athena_output_path)
            # Change string data type to timestamp via glue schema
            if self.aws_instance.check_query_status(execution_query_id) is True:
                timestamp_columns = [
                    'opened_at_timestamp',
                    'resolved_at_timestamp',
                    'sys_updated_timestamp',
                    'closed_timestamp',
                    'reopened_timestamp'
                ]
                self.aws_instance.update_table_columns_to_timestamp('semantic', 'view_daily_incident_pre_snapshot',
                                                                    timestamp_columns)

        else:

            # Load the Delta table as a DeltaTable
            delta_table = DeltaTable.forPath(self.spark, save_output_path)

            # Delete rows with the specified reporting_date
            delta_table.delete(f"reporting_date = '{self.formatted_reporting_date}'")

            # Append the new DataFrame to the Delta table
            df.write.format("delta").mode("append") \
                .partitionBy('reporting_date') \
                .save(save_output_path)

            # Vaccum the Delta table
            delta_table.vacuum(retentionHours=200)

        # create semantic daily view
        self.create_snapshot_view(save_output_path)
        self.logger.info("View 'view_daily_incident_snapshot' created successfully.")
        self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')

    def create_snapshot_view(self, output_path):
        # Load the Delta table into a DataFrame
        df_daily_incidents_pre_snapshot = self.spark.read.format("delta").load(output_path)

        # Register as a temporary view
        df_daily_incidents_pre_snapshot.createOrReplaceTempView("view_daily_incident_pre_snapshot")

        snapshot_view_query = """
        CREATE OR REPLACE VIEW view_daily_incident_snapshot AS 
        SELECT
          restaurant_id,
          restaurant_name,
          restaurant_full_name,
          incident_id,
          incident_short_description,
          incident_state,
          eod_incident_status,
          opened_at_date,
          CAST(opened_at_timestamp AS timestamp) AS opened_at_timestamp,
          resolved_at_date,
          CAST(resolved_at_timestamp AS timestamp) AS resolved_at_timestamp,
          first_value(incident_priority_local) OVER (PARTITION BY incident_id ORDER BY CAST(sys_updated_timestamp AS timestamp) DESC) AS incident_priority_local,
          incident_priority_global,
          incident_category,
          incident_subcategory,
          assignment_group,
          service_offering,
          service_vendor,
          reporting_date,
          sys_updated_date,
          closed_date,
          CAST(sys_updated_timestamp AS timestamp) AS sys_updated_timestamp,
          CAST(closed_timestamp AS timestamp) AS closed_timestamp,
          reopened_date,
          CAST(reopened_timestamp AS timestamp) AS reopened_timestamp,
          hold_reason,
          contact_type,
          impact,
          severity,
          urgency,
          active_flag
        FROM
            view_daily_incident_pre_snapshot
        WHERE (NOT (Incident_id IN (SELECT DISTINCT Incident_id
        FROM
            view_daily_incident_pre_snapshot
        WHERE (incident_state IN ('Cancelled', 'Duplicate'))
        )))
        """
        execution_query_id = self.aws_instance.create_athena_view(
            'semantic',
            'view_daily_incident_snapshot', snapshot_view_query,
            self.athena_output_path
        )

        # Check query status and log accordingly
        if self.aws_instance.check_query_status(execution_query_id):
            self.logger.info("View 'view_daily_incident_snapshot' created successfully.")
            self.logger.info(f'Finished running the {self.__class__.__name__} pipeline!')
        else:
            self.logger.error("Failed to create view 'view_daily_incident_snapshot'.")
            self.logger.info(f'Failed running the {self.__class__.__name__} pipeline!')
