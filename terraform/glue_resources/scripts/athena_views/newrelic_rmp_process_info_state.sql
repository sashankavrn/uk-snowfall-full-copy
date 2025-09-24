-- This view depends on the below table:
-- "uk_snowfall_processed"."newrelic_rmp_process_info"

CREATE OR REPLACE VIEW newrelic_rmp_process_info_state AS
WITH ranked_service_name AS (
    SELECT 
        *,
        RANK() OVER (PARTITION BY service_name ORDER BY api_exe_timestamp_utc DESC) AS rank
    FROM "uk_snowfall_processed"."newrelic_rmp_process_info"
)
SELECT 
    restaurant_number,
    device,
    host_name,
    service_name,
    CASE 
        WHEN api_exe_timestamp_utc = ( 
            SELECT MAX(api_exe_timestamp_utc) 
            FROM uk_snowfall_processed.newrelic_rmp_process_info
        ) THEN 'running'
        ELSE 'stopped'
    END AS state,
    api_exe_timestamp_utc      
FROM ranked_service_name
WHERE rank = 1;