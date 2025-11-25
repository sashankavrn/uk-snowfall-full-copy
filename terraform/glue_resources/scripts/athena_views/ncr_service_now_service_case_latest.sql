-- This view depends on the below table:
-- "uk_snowfall_processed"."ncr_service_now_service_case"

CREATE OR REPLACE VIEW "uk_snowfall_semantic"."ncr_service_now_service_case_latest" AS
WITH latest_cases AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (PARTITION BY case_number ORDER BY sys_updated_timestamp_utc DESC) As row_num
    FROM "uk_snowfall_processed"."ncr_service_now_service_case"
)
SELECT 
    *
FROM latest_cases
WHERE row_num = 1;