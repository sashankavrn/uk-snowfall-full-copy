-- This view depends on the below table:
-- "uk_snowfall_processed"."newrelic_rmp_device_info"

CREATE OR REPLACE VIEW newrelic_rmp_device_info_latest AS
WITH ranked_devices AS (
    SELECT 
        *,
        RANK() OVER (PARTITION BY host_name ORDER BY sys_updated_timestamp DESC) AS rank
    FROM "uk_snowfall_processed"."newrelic_rmp_device_info"
)
SELECT 
    restaurant_number,             
    device,                    
    host_name,                 
    instance_type,             
    kernel_version,            
    linux_distribution,        
    operating_system,          
    windows_family,            
    windows_platform,          
    windows_version,           
    sys_updated_timestamp,     
    sys_updated_date,          
    sys_updated_year,          
    sys_updated_month          
FROM ranked_devices
WHERE rank = 1;