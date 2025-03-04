--This view depends on below table
    --"uk_snowfall_processed"."amazon_connect"

CREATE OR REPLACE VIEW "view_daily_amazon_connect_snapshot" AS
SELECT
  file_upload_date reporting_date
, Queue call_queue
, contacts_answered_in_15_seconds calls_handled_within_15_seconds
, contacts_answered_in_30_seconds calls_handled_within_30_seconds
, contacts_answered_in_45_seconds calls_handled_within_45_seconds
, contacts_handled_incoming calls_handled
, contacts_incoming calls_offered
, (contacts_abandoned - contacts_abandoned_in_45_seconds) calls_abandoned
, CAST((average_queue_answer_time * contacts_handled_incoming) AS BIGINT) total_customer_duration_seconds
, CAST((average_handle_time * contacts_handled_incoming) AS BIGINT) total_call_duration_seconds
, (contacts_answered_in_45_seconds / (contacts_incoming - contacts_abandoned_in_45_seconds)) grade_of_service
FROM
  uk_snowfall_processed.amazon_connect