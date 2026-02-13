
CREATE OR REPLACE VIEW "uk_snowfall_semantic"."vw_rfm_store_hours_by_channel" AS
WITH latest AS (
    SELECT
        restaurant_number,
        MAX(file_timestamp_utc) AS max_ts
    FROM "uk_snowfall_preparation"."service_agent_store_db"
    WHERE restaurant_number < 4000
      AND CAST(file_timestamp_utc AS DATE) = CURRENT_DATE  -- today in UTC
    GROUP BY restaurant_number
),
src AS (
    SELECT
        s.restaurant_number,
        s.file_timestamp_utc,
        CAST(json_parse(s.storedb_storeprofile_storehours_hours) AS array(json)) AS areas
    FROM "uk_snowfall_preparation"."service_agent_store_db" s
    JOIN latest l
      ON s.restaurant_number = l.restaurant_number
     AND s.file_timestamp_utc = l.max_ts
    WHERE s.storedb_storeprofile_storehours_hours IS NOT NULL
)
, area_expanded AS (
    SELECT
        s.restaurant_number,
        s.file_timestamp_utc,
        a AS area_json,
        json_extract_scalar(a, '$._areaName') AS area_name,
        CAST(json_extract(a, '$.Weekday') AS array(json)) AS weekdays
    FROM src s
    CROSS JOIN UNNEST (s.areas) AS t(a)
)
, weekday_expanded AS (
    SELECT
        ae.restaurant_number,
        ae.file_timestamp_utc,
        ae.area_name,
        CASE
            WHEN ae.area_name = 'Delivery' THEN 'UberEATS'
            WHEN ae.area_name = 'Curbside' THEN 'Click and Serve'
            WHEN ae.area_name = 'DriveThru' THEN 'Drive Thru'
            WHEN ae.area_name = 'Lobby'
                 AND lower(NULLIF(json_extract_scalar(w, '$._saleType'), '')) = 'takeout'
                 THEN 'Take-Out'
            WHEN ae.area_name = 'Lobby'
                 AND lower(NULLIF(json_extract_scalar(w, '$._saleType'), '')) = 'eatin'
                 THEN 'Eat-In'
            ELSE ae.area_name
        END AS channel,
        json_extract_scalar(w, '$._name') AS weekday_name,
        json_extract_scalar(w, '$._openTime')  AS open_time,
        json_extract_scalar(w, '$._closeTime') AS close_time,
        NULLIF(json_extract_scalar(w, '$._saleType'), '') AS sale_type,
        -- Handle _closed = true (treat day as "Closed")
        (lower(coalesce(json_extract_scalar(w, '$._closed'), 'false')) = 'true') AS is_closed
    FROM area_expanded ae
    CROSS JOIN UNNEST (ae.weekdays) AS t(w)
    WHERE NOT (
        ae.area_name = 'Lobby'
        AND lower(NULLIF(json_extract_scalar(w, '$._saleType'), '')) NOT IN ('takeout', 'eatin')
    )
)
SELECT
    restaurant_number,
    file_timestamp_utc,
    area_name,
    channel,
    MAX(CASE WHEN lower(weekday_name) = 'monday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS monday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'tuesday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS tuesday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'wednesday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS wednesday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'thursday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS thursday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'friday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS friday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'saturday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS saturday_opening_times,
    MAX(CASE WHEN lower(weekday_name) = 'sunday'
        THEN CASE WHEN is_closed THEN 'Closed'
                  ELSE concat(trim(open_time), '-', trim(close_time)) END END) AS sunday_opening_times
FROM weekday_expanded
GROUP BY restaurant_number, file_timestamp_utc, area_name, channel
ORDER BY restaurant_number, channel;
