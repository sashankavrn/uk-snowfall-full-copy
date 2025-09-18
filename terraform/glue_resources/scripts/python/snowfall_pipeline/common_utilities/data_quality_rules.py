dq_rules = {

    "location": """Rules = [
        ColumnCount <= 80,
        RowCount > 0,
        IsComplete "sys_created_on"
        ]""",

    "location_hierarchy":"""Rules = [
        ColumnCount <= 180,
        RowCount > 0,
        IsComplete "STORE_NUMBER",
        IsComplete "STORE_NAME"
        ]""",

    "incidents":"""Rules = [
        ColumnCount <= 250,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
        ]""",

    "amazon_connect": """Rules = [
        ColumnCount <= 120,
        RowCount > 0,
        IsComplete "queue",
        IsComplete "file_upload_date"
    ]""" ,

    "adj_trading_hours": """Rules = [
        ColumnCount <= 12,
        RowCount > 0,
        IsComplete "STORE_NUMBER",
        IsComplete "CHANNEL"
    ]""",

    "change_request": """Rules = [
        ColumnCount <= 133,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",

    "problem_record": """Rules = [
        ColumnCount <= 95,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""" ,

    "service_offering": """Rules = [
        ColumnCount <= 125,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",

    "service_request": """Rules = [
        ColumnCount <= 95,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",

    "sys_user_group": """Rules = [
        ColumnCount <= 20,
        RowCount > 0,
        IsComplete "sys_id",
        IsComplete "sys_created_on"
    ]""",

    "sys_user": """Rules = [
        ColumnCount <= 65,
        RowCount > 0,
        IsComplete "sys_id",
        IsComplete "sys_created_on"
    ]""",
    
    "trading_hours": """Rules = [
        ColumnCount <= 10,
        RowCount > 0,
        IsComplete "STORE_NUMBER",
        IsComplete "CHANNEL"
    ]""",
    "meraki_device_info": """Rules = [
        ColumnCount <= 23,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "meraki_client_info": """Rules = [
        ColumnCount <= 40,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "newrelic_rmp_device_info": """Rules = [
        ColumnCount <= 12,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "newrelic_rmp_device_metrics": """Rules = [
        ColumnCount <= 40,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "newrelic_digital_gma_foe_response": """Rules = [
        ColumnCount <= 7,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "newrelic_rmp_process_info": """Rules = [
        ColumnCount <= 7,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
    "newrelic_digital_3po_foe_response": """Rules = [
        ColumnCount <= 8,
        RowCount > 0,
        IsComplete "restaurant_number"
    ]""",
        "ncr_service_now_service_case": """Rules = [
        ColumnCount <= 310,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",
    "ncr_service_now_incident":"""Rules = [
        ColumnCount <= 295,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",
    "ncr_service_now_incident_task":"""Rules = [
        ColumnCount <= 195,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",
        "ncr_service_now_problem_record": """Rules = [
        ColumnCount <= 210,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",
        "ncr_service_now_change_request": """Rules = [
        ColumnCount <= 250,
        RowCount > 0,
        IsComplete "number",
        IsComplete "sys_created_on"
    ]""",
    "ncr_service_now_knowledge_base":"""Rules = [
        ColumnCount <= 65,
        RowCount > 0,
        IsComplete "master_customer_id",
        IsComplete "sys_created_on"
    ]""",
    "store_db_config":"""Rules = [
        ColumnCount <= 115,
        RowCount > 0
    ]"""
}