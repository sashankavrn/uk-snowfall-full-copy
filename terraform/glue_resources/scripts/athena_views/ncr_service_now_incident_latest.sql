-- This view depends on the below table:
-- "uk_snowfall_processed"."ncr_service_now_incident"

CREATE OR REPLACE VIEW "uk_snowfall_semantic"."ncr_service_now_incident_latest" AS
WITH latest_incidents AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY incident_number ORDER BY sys_updated_timestamp_utc DESC) As row_num
    FROM "uk_snowfall_processed"."ncr_service_now_incident"
)
SELECT 
    *
FROM latest_incidents
WHERE row_num = 1;