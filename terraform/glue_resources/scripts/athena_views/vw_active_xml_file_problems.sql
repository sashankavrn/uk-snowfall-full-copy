-- Creates a view of restaurants that have active XML file problems.
-- A problem is defined as the latest record for a given (location, filename)
-- where the error flag indicates an issue (error = 'True').
-- The view aggregates all problem filenames and messages into a single
-- problem summary per restaurant_number.

CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_active_xml_file_problems AS
WITH latest_per_file AS (
    SELECT
        filename,
        location,
        restaurant_number,
        message,
        error,
        ingest_file_timestamp_utc,
        ROW_NUMBER() OVER (
            PARTITION BY location, filename
            ORDER BY ingest_file_timestamp_utc DESC
        ) AS rn
    FROM uk_snowfall_preparation.service_agent_xml_file_errors
),
active_problems AS (
    -- Only latest record per (location, filename) AND only those where error='True'
    SELECT
        restaurant_number,
        filename,
        message
    FROM latest_per_file
    WHERE rn = 1
      AND error = 'True'
)
SELECT
    restaurant_number,
    array_join(
        array_agg(
            CONCAT(filename, ': ', message)
        ),
        ', '
    ) AS problem_summary
FROM active_problems
GROUP BY restaurant_number;