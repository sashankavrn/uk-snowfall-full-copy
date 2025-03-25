-- This view depends on the below table:
-- "uk_snowfall_processed"."meraki_device_info"

CREATE OR REPLACE VIEW meraki_device_info_latest AS
WITH ranked_devices AS (
    SELECT 
        *,
        RANK() OVER (PARTITION BY serial_number ORDER BY sys_updated_timestamp DESC) AS rank
    FROM "uk_snowfall_processed"."meraki_device_info"
)
SELECT 
    restaurant_number,             
    device_name,               
    serial_number,             
    mac_address,               
    network_id,                
    product_type,              
    model,                     
    address,                   
    latitude,                  
    longitude,                 
    notes,                     
    tags,                      
    wan1_ip,                   
    wan2_ip,                   
    config_updated_at,         
    firmware_version,          
    device_url,                
    monitoring_version,        
    running_software_version,  
    sys_updated_timestamp,     
    sys_updated_date,          
    sys_updated_year,          
    sys_updated_month          
FROM ranked_devices
WHERE rank = 1;