CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_rfm_ods_store_hours_diff_by_channel AS
SELECT
    rfm.restaurant_number,
    rfm.channel AS channel_rfm,
    ods.channel AS channel_ods,
    CASE WHEN rfm.monday_opening_times    IS DISTINCT FROM ods.monday_opening_times    THEN rfm.monday_opening_times    ELSE NULL END AS monday_rfm,
    CASE WHEN rfm.monday_opening_times    IS DISTINCT FROM ods.monday_opening_times    THEN ods.monday_opening_times    ELSE NULL END AS monday_ods,
    CASE WHEN rfm.tuesday_opening_times   IS DISTINCT FROM ods.tuesday_opening_times   THEN rfm.tuesday_opening_times   ELSE NULL END AS tuesday_rfm,
    CASE WHEN rfm.tuesday_opening_times   IS DISTINCT FROM ods.tuesday_opening_times   THEN ods.tuesday_opening_times   ELSE NULL END AS tuesday_ods,
    CASE WHEN rfm.wednesday_opening_times IS DISTINCT FROM ods.wednesday_opening_times THEN rfm.wednesday_opening_times ELSE NULL END AS wednesday_rfm,
    CASE WHEN rfm.wednesday_opening_times IS DISTINCT FROM ods.wednesday_opening_times THEN ods.wednesday_opening_times ELSE NULL END AS wednesday_ods,
    CASE WHEN rfm.thursday_opening_times  IS DISTINCT FROM ods.thursday_opening_times  THEN rfm.thursday_opening_times  ELSE NULL END AS thursday_rfm,
    CASE WHEN rfm.thursday_opening_times  IS DISTINCT FROM ods.thursday_opening_times  THEN ods.thursday_opening_times  ELSE NULL END AS thursday_ods,
    CASE WHEN rfm.friday_opening_times    IS DISTINCT FROM ods.friday_opening_times    THEN rfm.friday_opening_times    ELSE NULL END AS friday_rfm,
    CASE WHEN rfm.friday_opening_times    IS DISTINCT FROM ods.friday_opening_times    THEN ods.friday_opening_times    ELSE NULL END AS friday_ods,
    CASE WHEN rfm.saturday_opening_times  IS DISTINCT FROM ods.saturday_opening_times  THEN rfm.saturday_opening_times  ELSE NULL END AS saturday_rfm,
    CASE WHEN rfm.saturday_opening_times  IS DISTINCT FROM ods.saturday_opening_times  THEN ods.saturday_opening_times  ELSE NULL END AS saturday_ods,
    CASE WHEN rfm.sunday_opening_times    IS DISTINCT FROM ods.sunday_opening_times    THEN rfm.sunday_opening_times    ELSE NULL END AS sunday_rfm,
    CASE WHEN rfm.sunday_opening_times    IS DISTINCT FROM ods.sunday_opening_times    THEN ods.sunday_opening_times    ELSE NULL END AS sunday_ods
FROM uk_snowfall_semantic.vw_rfm_store_hours_by_channel rfm
JOIN uk_snowfall_semantic.vw_ods_trading_hours_latest ods
  ON rfm.restaurant_number = ods.store_number
 AND rfm.channel = ods.channel
WHERE
       rfm.monday_opening_times    IS DISTINCT FROM ods.monday_opening_times
    OR rfm.tuesday_opening_times   IS DISTINCT FROM ods.tuesday_opening_times
    OR rfm.wednesday_opening_times IS DISTINCT FROM ods.wednesday_opening_times
    OR rfm.thursday_opening_times  IS DISTINCT FROM ods.thursday_opening_times
    OR rfm.friday_opening_times    IS DISTINCT FROM ods.friday_opening_times
    OR rfm.saturday_opening_times  IS DISTINCT FROM ods.saturday_opening_times
    OR rfm.sunday_opening_times    IS DISTINCT FROM ods.sunday_opening_times;
    
