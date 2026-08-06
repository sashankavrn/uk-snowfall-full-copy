CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_service_agent_xml_file_errors_latest AS
WITH ranked_data AS (
    SELECT
        filename,
        location,
        -- Convert string to boolean
        CASE
            WHEN lower(CAST(error AS VARCHAR)) = 'true' THEN TRUE
            WHEN lower(CAST(error AS VARCHAR)) = 'false' THEN FALSE
            ELSE NULL
        END AS error,
        message,
        host_name,
        ingest_file_timestamp_utc,
        restaurant_number,
        device_name,
        cdc_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY location, filename
            ORDER BY ingest_file_timestamp_utc DESC
        ) AS rn

    FROM uk_snowfall_preparation.service_agent_xml_file_errors
)

SELECT
    *
FROM ranked_data
WHERE rn = 1;