CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_store_currently_open AS
WITH runtime AS (
    SELECT
        current_timestamp AT TIME ZONE 'Europe/London' AS now_ts,

        CASE
            WHEN hour(current_timestamp AT TIME ZONE 'Europe/London') < 5
                THEN lower(
                    format_datetime(
                        (current_timestamp AT TIME ZONE 'Europe/London') - INTERVAL '1' DAY,
                        'EEEE'
                    )
                )
            ELSE lower(
                format_datetime(
                    current_timestamp AT TIME ZONE 'Europe/London',
                    'EEEE'
                )
            )
        END AS business_weekday,

        CAST(
            date_format(
                current_timestamp AT TIME ZONE 'Europe/London',
                '%H:%i'
            ) AS TIME
        ) AS now_time
),

hours AS (
    SELECT
        t.store_number,
        t.channel,
        r.now_time,
        r.business_weekday,
        CASE r.business_weekday
            WHEN 'monday'    THEN t.monday_opening_times
            WHEN 'tuesday'   THEN t.tuesday_opening_times
            WHEN 'wednesday' THEN t.wednesday_opening_times
            WHEN 'thursday'  THEN t.thursday_opening_times
            WHEN 'friday'    THEN t.friday_opening_times
            WHEN 'saturday'  THEN t.saturday_opening_times
            WHEN 'sunday'    THEN t.sunday_opening_times
        END AS opening_window
    FROM uk_snowfall_processed.ods_adj_trading_hours t
    CROSS JOIN runtime r
),

evaluated AS (
    SELECT
        store_number,
        channel,
        CASE
            WHEN opening_window IN ('Closed', 'No') THEN FALSE
            WHEN opening_window = '24h' THEN TRUE
            ELSE
                CASE
                    -- same‑day window (e.g. 07:00‑21:00)
                    WHEN
                        CAST(substr(opening_window, 1, 5) AS TIME)
                        <= CAST(substr(opening_window, 7, 5) AS TIME)
                    THEN
                        now_time BETWEEN
                            CAST(substr(opening_window, 1, 5) AS TIME)
                            AND
                            CAST(substr(opening_window, 7, 5) AS TIME)

                    -- crosses midnight (e.g. 06:00‑01:00)
                    ELSE
                        now_time >= CAST(substr(opening_window, 1, 5) AS TIME)
                        OR
                        now_time <= CAST(substr(opening_window, 7, 5) AS TIME)
                END
        END AS channel_is_open
    FROM hours
)

SELECT
    store_number,

    /* Overall: any channel open */
    MAX(channel_is_open) AS overall,

    /* In‑store: Eat‑In, Take‑Out, Table Service */
    MAX(
        CASE
            WHEN channel IN ('Eat-In', 'Take-Out')
                THEN channel_is_open
            ELSE FALSE
        END
    ) AS instore,

    /* Drive Thru */
    MAX(
        CASE
            WHEN channel = 'Drive Thru'
                THEN channel_is_open
            ELSE FALSE
        END
    ) AS drivethru,

    /* Delivery platforms */
    MAX(
        CASE
            WHEN channel IN ('UberEATS', 'Just Eat', 'Deliveroo')
                THEN channel_is_open
            ELSE FALSE
        END
    ) AS delivery,

    /* Curbside */
    MAX(
        CASE
            WHEN channel = 'Click and Serve'
                THEN channel_is_open
            ELSE FALSE
        END
    ) AS curbside

FROM evaluated
GROUP BY store_number;