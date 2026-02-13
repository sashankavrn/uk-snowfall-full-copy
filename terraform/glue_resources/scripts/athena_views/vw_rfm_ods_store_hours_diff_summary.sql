
CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_rfm_ods_store_hours_diff_summary AS
SELECT
    restaurant_number,
    CASE
        WHEN diff_days = 1 AND diff_channels = 1
            THEN CONCAT('Restaurant ', CAST(restaurant_number AS VARCHAR),
                        ' has 1 day difference in 1 channel for opening and/or closing hours')
        WHEN diff_days = 1 AND diff_channels > 1
            THEN CONCAT('Restaurant ', CAST(restaurant_number AS VARCHAR),
                        ' has 1 day difference across multiple channels for opening and/or closing hours')
        WHEN diff_days > 1 AND diff_channels = 1
            THEN CONCAT('Restaurant ', CAST(restaurant_number AS VARCHAR),
                        ' has multiple day differences in 1 channel for opening and/or closing hours')
        ELSE CONCAT('Restaurant ', CAST(restaurant_number AS VARCHAR),
                    ' has multiple day differences across multiple channels for opening and/or closing hours')
    END AS description,
    diff_days,
    diff_channels
FROM (
    SELECT
        restaurant_number,
        COUNT(DISTINCT channel_rfm) AS diff_channels,
        SUM(
            CASE WHEN monday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN tuesday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN wednesday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN thursday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN friday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN saturday_rfm IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN sunday_rfm IS NOT NULL THEN 1 ELSE 0 END
        ) AS diff_days
    FROM uk_snowfall_semantic.vw_rfm_ods_store_hours_diff_by_channel
    GROUP BY restaurant_number
) summary;
