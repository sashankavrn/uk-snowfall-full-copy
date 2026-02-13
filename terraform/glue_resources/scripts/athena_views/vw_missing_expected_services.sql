-- Creates a view of hosts that are missing “expected” services.
-- Expected = services that run on at least 50% of hosts for that device_type.

CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_missing_expected_services AS
WITH latest_extract AS (
    SELECT
        restaurant_number,
        device,
        device_type,
        host_name,
        service_name,
        new_relic_timestamp_latest_utc,
        ROW_NUMBER() OVER (
            PARTITION BY host_name, service_name
            ORDER BY new_relic_timestamp_latest_utc DESC
        ) AS rn
    FROM uk_snowfall_processed.newrelic_rmp_process_info
),
filtered_latest AS (
    SELECT *
    FROM latest_extract
    WHERE rn = 1
),
device_type_counts AS (
    SELECT
        device_type,
        COUNT(DISTINCT host_name) AS total_hosts
    FROM filtered_latest
    GROUP BY device_type
),
service_counts AS (
    SELECT
        device_type,
        service_name,
        COUNT(DISTINCT host_name) AS hosts_running_service
    FROM filtered_latest
    GROUP BY device_type, service_name
),
expected_services AS (
    SELECT
        sc.device_type,
        sc.service_name
    FROM service_counts sc
    JOIN device_type_counts dtc
        ON sc.device_type = dtc.device_type
    WHERE sc.hosts_running_service >= dtc.total_hosts * 0.5
),
hosts_by_type AS (
    SELECT DISTINCT
        restaurant_number,
        device,
        device_type,
        host_name
    FROM filtered_latest
),
all_expected AS (
    SELECT DISTINCT
        h.restaurant_number,
        h.device,
        h.device_type,
        h.host_name,
        e.service_name AS expected_service
    FROM hosts_by_type h
    JOIN expected_services e
        ON h.device_type = e.device_type
),
present_services AS (
    SELECT
        host_name,
        service_name
    FROM filtered_latest
)
SELECT
    a.restaurant_number,
    a.device,
    a.host_name,
    a.expected_service AS service_name
FROM all_expected a
LEFT JOIN present_services p
    ON a.host_name = p.host_name
   AND a.expected_service = p.service_name
WHERE p.service_name IS NULL
ORDER BY a.restaurant_number, a.host_name, a.expected_service;