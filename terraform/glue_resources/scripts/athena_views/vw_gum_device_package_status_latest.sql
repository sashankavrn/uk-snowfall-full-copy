CREATE OR REPLACE VIEW uk_snowfall_semantic.vw_gum_device_package_status_latest AS
WITH latest_per_store AS (
    SELECT *
    FROM (
        SELECT
            *,
            row_number() OVER (
                PARTITION BY restaurant_number
                ORDER BY ingest_file_timestamp_utc DESC
            ) AS rn
        FROM uk_snowfall_preparation.service_agent_gum_all_devices
    ) t
    WHERE rn = 1
),

device_array AS (
    SELECT
        restaurant_number,
        ingest_file_timestamp_utc,
        d AS device_json
    FROM latest_per_store
    CROSS JOIN UNNEST(
        CAST(json_parse(device) AS array(json))
    ) AS t(d)
),

updates AS (
    SELECT
        restaurant_number,
        json_extract_scalar(device_json, '$._name') AS device,
        json_extract_scalar(device_json, '$._hostname') AS hostname,
        status,
        pkg
    FROM device_array

    CROSS JOIN UNNEST(
        ARRAY['installed','failed','not_applicable','bad_crc']
    ) AS t(status)

    CROSS JOIN UNNEST(
        CAST(
            COALESCE(
                CASE status
                    WHEN 'installed' THEN 
                        COALESCE(
                            try(json_extract(device_json,'$.gum_log.updates.installed.package')),
                            json_parse('[]')
                        )
                    WHEN 'not_applicable' THEN
                        COALESCE(
                            try(json_extract(device_json,'$.gum_log.updates.not_applicable.package')),
                            json_parse('[]')
                        )
                    WHEN 'failed' THEN 
                        COALESCE(
                            try(json_extract(device_json,'$.gum_log.updates.failed.package')),
                            json_parse('[]')
                        )
                    WHEN 'bad_crc' THEN 
                        COALESCE(
                            try(json_extract(device_json,'$.gum_log.updates.bad_crc.package')),
                            json_parse('[]')
                        )
                END,
                json_parse('[]')
            ) AS array(json)
        )
    ) AS t2(pkg)
)

SELECT
    restaurant_number,
    device,
    hostname,
    status,

    json_extract_scalar(pkg, '$._package_id')         AS package_id,
    json_extract_scalar(pkg, '$._original_file_name') AS original_file_name,
    json_extract_scalar(pkg, '$._installation_date') AS installation_date,
    CAST(json_extract_scalar(pkg, '$._installer_exit_code') AS INTEGER) AS installer_exit_code,
    CAST(json_extract_scalar(pkg, '$._file_size') AS BIGINT) AS file_size,
    CAST(json_extract_scalar(pkg, '$._major_ver_no') AS INTEGER) AS major_ver_no,
    CAST(json_extract_scalar(pkg, '$._minor_ver_no') AS INTEGER) AS minor_ver_no,

    regexp_replace(
        regexp_replace(
            regexp_replace(json_extract_scalar(pkg, '$._comment'), '&amp;quot;', '"'),
            '&amp;apos;', ''''
        ),
        '&amp;amp;', '&'
    ) AS comment

FROM updates;