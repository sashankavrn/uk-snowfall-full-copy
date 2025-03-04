--This view depends on below table
    --"uk_snowfall_semantic"."view_daily_franchisee_restaurant_incidents"

CREATE OR REPLACE VIEW "view_daily_franchisee_regional_incidents" AS
SELECT
  count(DISTINCT restaurant_id) "restaurant_count"
, count(DISTINCT incident_id) "incident_count"
, incident_state
, eod_incident_status
, opened_at_date
, resolved_at_date
, incident_priority_local
, incident_priority_global  
, incident_category
, incident_subcategory
, service_offering
, SUM((CASE WHEN (CAST(engineer_flag AS varchar) = 'false') THEN 0 ELSE 1 END)) "engineer_visits"
, region
, (CASE WHEN (Lower(region) IN ('mcopco', 'roadchef')) THEN region ELSE 'Other' END) "region_group"
FROM
  "uk_snowfall_semantic"."view_daily_franchisee_restaurant_incidents"
GROUP BY incident_state, eod_incident_status, opened_at_date, resolved_at_date, incident_priority_local, incident_priority_global, incident_category, incident_subcategory, service_offering, region, (CASE WHEN (Lower(region) IN ('mcopco', 'roadchef')) THEN region ELSE 'Other' END)
ORDER BY restaurant_count DESC
