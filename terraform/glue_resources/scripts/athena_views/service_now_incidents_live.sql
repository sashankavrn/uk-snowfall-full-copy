--This view depends on below tables
    --"uk_snowfall_processed"."service_now_incident_daily"
    --"uk_snowfall_processed"."service_now_incident_intraday"

CREATE OR REPLACE VIEW "service_now_incidents_live" AS
WITH
  combined AS (
   SELECT
     *
   , ROW_NUMBER() OVER (PARTITION BY incident_number ORDER BY sys_updated_timestamp DESC) row_num
   FROM
     (
      SELECT
        restaurant_id
      , restaurant_name
      , incident_number
      , short_description
      , state
      , opened_date
      , CAST(opened_timestamp AS timestamp) opened_timestamp
      , resolved_at_date
      , CAST(resolved_at_timestamp AS timestamp) resolved_at_timestamp
      , priority
      , category
      , subcategory
      , assignment_group
      , service_offering
      , u_vendor
      , sys_updated_date
      , closed_date
      , CAST(sys_updated_timestamp AS timestamp) sys_updated_timestamp
      , CAST(closed_timestamp AS timestamp) closed_timestamp
      , reopened_time_date
      , CAST(reopened_timestamp AS timestamp) reopened_timestamp
      , hold_reason
      , contact_type
      , impact
      , severity
      , urgency
      , active_flag
      FROM
        "uk_snowfall_processed"."service_now_incident_daily"
UNION       SELECT
        restaurant_id
      , restaurant_name
      , incident_number
      , short_description
      , state
      , opened_date
      , CAST(opened_timestamp AS timestamp) opened_timestamp
      , resolved_at_date
      , CAST(resolved_at_timestamp AS timestamp) resolved_at_timestamp
      , priority
      , category
      , subcategory
      , assignment_group
      , service_offering
      , u_vendor
      , sys_updated_date
      , closed_date
      , CAST(sys_updated_timestamp AS timestamp) sys_updated_timestamp
      , CAST(closed_timestamp AS timestamp) closed_timestamp
      , reopened_time_date
      , CAST(reopened_timestamp AS timestamp) reopened_timestamp
      , hold_reason
      , contact_type
      , impact
      , severity
      , urgency
      , active_flag
      FROM
        "uk_snowfall_processed"."service_now_incident_intraday"
   )  AllIncidents
)
SELECT *
FROM
  combined
WHERE (row_num = 1)