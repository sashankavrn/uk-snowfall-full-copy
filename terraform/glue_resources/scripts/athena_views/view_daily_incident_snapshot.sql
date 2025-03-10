--This view depends on below table
    --"uk_snowfall_semantic"."view_daily_incident_pre_snapshot"
-- testing
CREATE OR REPLACE VIEW "view_daily_incident_snapshot" AS
SELECT
  restaurant_id
, restaurant_name
, restaurant_full_name
, incident_id
, incident_short_description
, incident_state
, eod_incident_status
, opened_at_date
, CAST(opened_at_timestamp AS timestamp) opened_at_timestamp
, resolved_at_date
, CAST(resolved_at_timestamp AS timestamp) resolved_at_timestamp
, first_value(incident_priority_local) OVER (PARTITION BY incident_id ORDER BY CAST(sys_updated_timestamp AS timestamp) DESC) incident_priority_local
, incident_priority_global
, incident_category
, incident_subcategory
, assignment_group
, service_offering
, service_vendor
, reporting_date
, sys_updated_date
, closed_date
, CAST(sys_updated_timestamp AS timestamp) sys_updated_timestamp
, CAST(closed_timestamp AS timestamp) closed_timestamp
, reopened_date
, CAST(reopened_timestamp AS timestamp) reopened_timestamp
, hold_reason
, contact_type
, impact
, severity
, urgency
, active_flag
FROM
  view_daily_incident_pre_snapshot
WHERE (NOT (Incident_id IN (SELECT DISTINCT Incident_id
FROM
  uk_snowfall_semantic.view_daily_incident_pre_snapshot
WHERE (incident_state IN ('Cancelled', 'Duplicate'))
)))