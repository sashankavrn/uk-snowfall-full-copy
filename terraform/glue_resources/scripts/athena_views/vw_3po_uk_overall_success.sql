CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_3po_uk_overall_success AS
WITH latest AS (
    SELECT MAX(cdc_timestamp) AS max_ts
    FROM uk_snowfall_processed.newrelic_digital_3po_foe_response
),
filtered AS (
    SELECT *
    FROM uk_snowfall_processed.newrelic_digital_3po_foe_response
    WHERE cdc_timestamp = (SELECT max_ts FROM latest)
      AND restaurant_number < 7000   -- UK filter
),
agg AS (
    SELECT 
        SUM(CASE WHEN foe_response = 0 AND "3po_description" = 'No error'
                 THEN count ELSE 0 END) AS success_count,
        SUM(count) AS total_count
    FROM filtered
)
SELECT
    success_count,
    total_count,
    ROUND(((success_count * 1.0) / total_count) * 100, 2) AS success_rate_pct
FROM agg;