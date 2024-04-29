# uk-snowfall Project Readme

## Overview:
The uk-snowfall project aims to create a comprehensive data lakehouse leveraging AWS services, particularly Glue, to ingest, process, and analyze data related to McDonald's restaurants and associated incidents. The infrastructure is managed and provisioned using Terraform, ensuring consistency and scalability.

## Modules:
The project is organized into three main modules:

1. **core_delta_lake**: This module is responsible for provisioning core resources such as S3 buckets, Lambda functions, and other fundamental components required for the data lakehouse infrastructure.

2. **glue_resources**: The glue_resources module is where the majority of changes and customizations occur. It includes pipeline scripts for data ingestion, transformation, and management using AWS Glue services.

3. **other_resources**: This module encompasses additional resources like EventBridge triggers and soon-to-be-implemented Athena table creations. It complements the core_delta_lake and glue_resources modules by adding supplementary functionalities and integrations.

## Pre-Deployment Requirements:
Before deploying the infrastructure, ensure that a ServiceNow connector is configured in AppFlow. This connector facilitates seamless integration with ServiceNow for incident management and data synchronization. Once configured, specify the connector profile name in the variables for seamless integration.

## Deployment Process:
1. Configure ServiceNow connector in AppFlow.
2. Specify connector profile name in variables.
3. Utilize Terraform to deploy infrastructure modules in the following sequence:
   a. core_delta_lake
   b. glue_resources
   c. other_resources
