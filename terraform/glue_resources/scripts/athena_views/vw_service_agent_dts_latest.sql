CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_service_agent_dts_latest AS
WITH ranked_data AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY restaurant_number, sensor
            ORDER BY ingest_file_timestamp_utc DESC
        ) AS rn
    FROM uk_snowfall_preparation.service_agent_dts_health_check
)
SELECT *
FROM ranked_data
WHERE rn = 1;
