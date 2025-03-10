--This view depends on below tables
    --"uk_snowfall_processed"."service_now_incident_daily"
    --"uk_snowfall_processed"."service_now_location"
    --"uk_snowfall_processed"."ods_location_hierarchy"
-- modifying to see if the lambda triggers
CREATE OR REPLACE VIEW "view_daily_restaurant_incident_hub" AS
SELECT
  restaurant_id
, restaurant_name
, restaurant_full_name
, restaurant_hierarchy_id
, incident_id
, incident_short_description
, incident_state
, eod_incident_status
, opened_at_date
, opened_at_timestamp
, resolved_at_date
, resolved_at_timestamp
, business_duration_seconds
, incident_priority_local
, incident_priority_global
, incident_category
, incident_subcategory
, assignment_group
, service_offering
, service_vendor
, service_vendor_ticket_id
, happy_signal_feedback_id
, happy_signal_score
, techsee_session_id
, techsee_flag
, vista_id
, vista_flag
, engineer_flag
, franchisee
, franchisee_email
, franchisee_id
, franchisee_hierarchy_id
, franchisee_manager
, restaurant_type
, drive_thru_flag
, country
, region
, city
, postcode
, longitude
, latitude
, sys_updated_date
, hold_reason
, contact_type
FROM
  (
   SELECT
     incident.restaurant_id restaurant_id
   , incident.restaurant_name restaurant_name
   , (CASE WHEN (incident.restaurant_id = -1) THEN incident.restaurant_name ELSE CONCAT(CAST(incident.restaurant_id AS varchar), ' ', incident.restaurant_name) END) restaurant_full_name
   , location_hierarchy.hierarchy_id restaurant_hierarchy_id
   , incident.incident_number incident_id
   , incident.short_description incident_short_description
   , incident.state incident_state
   , (CASE WHEN ((incident.opened_date = incident.resolved_at_date) AND (incident.opened_date = incident.closed_date)) THEN 'New and Resolved' ELSE incident.state END) eod_incident_status
   , incident.opened_date opened_at_date
   , CAST(incident.opened_timestamp AS timestamp) opened_at_timestamp
   , incident.resolved_at_date resolved_at_date
   , CAST(incident.resolved_at_timestamp AS timestamp) resolved_at_timestamp
   , incident.calendar_stc business_duration_seconds
   , incident.priority incident_priority_local
   , incident.priority incident_priority_global
   , incident.category incident_category
   , incident.subcategory incident_subcategory
   , incident.assignment_group assignment_group
   , incident.service_offering service_offering
   , incident.u_vendor service_vendor
   , incident.u_vendor_ticket service_vendor_ticket_id
   , incident.u_happysignal_feedback_number happy_signal_feedback_id
   , incident.u_happysignal_score happy_signal_score
   , incident.u_techsee_session techsee_session_id
   , (CASE WHEN (LENGTH(incident.u_techsee_sessionid) > 0) THEN true ELSE false END) techsee_flag
   , incident.u_vista_id vista_id
   , (CASE WHEN (LENGTH(incident.u_vista_id) > 0) THEN true ELSE false END) vista_flag
   , (CASE WHEN (incident.u_vendor = 'McD-UK Vista') THEN true WHEN (incident.u_vendor = 'McD UK - Partner - Acrelec') THEN true WHEN (incident.u_vendor = 'McD UK - Partner - Evoke') THEN true WHEN (incident.u_vendor = 'McD UK - Partner - Odema') THEN true ELSE false END) engineer_flag
   , location_hierarchy.oo_full_name franchisee
   , location_hierarchy.oo_email franchisee_email
   , location_hierarchy.oo_eid franchisee_id
   , location_hierarchy.oo_hierarchy_no franchisee_hierarchy_id
   , incident.u_franchisee_regional_manager franchisee_manager
   , location.location_type restaurant_type
   , location.u_drive_thru_flag drive_thru_flag
   , (CASE WHEN (location.country = 'Republic Of Ireland') THEN 'Republic of Ireland' WHEN (location.country = '') THEN 'N/A' WHEN (location.country IS NULL) THEN 'N/A' ELSE location.country END) country
   , location.u_rlg1 region
   , location.city city
   , location_hierarchy.postcode postcode
   , location_hierarchy.longitude longitude
   , location_hierarchy.latitude latitude
   , incident.sys_updated_date sys_updated_date
   , incident.hold_reason
   , incident.contact_type
   , rank() OVER (PARTITION BY incident.incident_number ORDER BY CAST(incident.sys_updated_timestamp AS timestamp) DESC) incident_rank
   FROM
     (("uk_snowfall_processed"."service_now_incident_daily" incident
   LEFT JOIN "uk_snowfall_processed"."service_now_location" location ON ((incident.restaurant_id = location.restaurant_id) AND (incident.restaurant_name = location.restaurant_name)))
   LEFT JOIN "uk_snowfall_processed"."ods_location_hierarchy" location_hierarchy ON (incident.restaurant_id = location_hierarchy.store_number))
)
WHERE (incident_rank = 1)
