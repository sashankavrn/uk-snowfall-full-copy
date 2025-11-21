-- This view depends on the below table:
-- "uk_snowfall_processed"."ncr_service_now_worknotes"

CREATE OR REPLACE VIEW "uk_snowfall_semantic"."ncr_service_now_work_notes_aggregated" AS
SELECT 
    number,
    array_join(
        array_agg(sys_created_timestamp || ' - ' || value ORDER BY sys_created_timestamp)
        FILTER (WHERE element = 'comments'),
        CHR(10)
    ) AS comments,
    array_join(
        array_agg(sys_created_timestamp || ' - ' || value ORDER BY sys_created_timestamp)
        FILTER (WHERE element = 'work_notes'),
        CHR(10)
    ) AS work_notes,
    array_join(
        array_agg(sys_created_timestamp || ' - ' || value ORDER BY sys_created_timestamp),
        CHR(10)
    ) AS comments_and_work_notes
FROM "uk_snowfall_processed"."ncr_service_now_worknotes"
GROUP BY number;