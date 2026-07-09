# uk-snowfall Project Readme

## Overview:
Snowfall 2.0 is the UK Snowfall data platform for ingesting, transforming and serving operational, infrastructure and incident datasets across multiple enterprise sources. The platform is built on AWS and uses Terraform for infrastructure management, Lambda for ingestion and routing, Glue for transformation, Delta Lake for storage and Athena for query access.

## Modules:
The project is organized into four main modules:

1. **core_delta_lake**: This module is responsible for provisioning core resources such as S3 buckets, Lambda functions, and other fundamental components required for the data lakehouse infrastructure.

2. **glue_resources**: The glue_resources module is where the majority of changes and customizations occur. It includes pipeline scripts for data ingestion, transformation, and management using AWS Glue services.

3. **other_resources**: This module encompasses additional resources like EventBridge triggers and soon-to-be-implemented Athena table creations. It complements the core_delta_lake and glue_resources modules by adding supplementary functionalities and integrations.

4. **datashare_resources**: This module provisions the datashare distribution layer, including datashare landing and processed buckets, transfer Lambdas, EventBridge integration and downstream sharing paths such as Tech360.

## Platform Flow:
Snowfall 2.0 follows a layered processing model:

1. Source systems land data into Snowfall landing buckets using AppFlow, scheduled Lambdas or API-driven ingress.
2. Landing trigger Lambdas classify and move files into the correct raw bucket paths.
3. EventBridge rules detect raw bucket object creation events and invoke dataset-specific Glue workflows.
4. Glue pipelines process data through preparation, processed and semantic layers using Delta Lake.
5. Athena is used to query curated outputs.
6. Datashare flows replicate selected processed or shared datasets into datashare-specific buckets for downstream distribution.

## Pre-Deployment Requirements:
Before deploying the infrastructure, ensure that a ServiceNow connector is configured in AppFlow. This connector facilitates seamless integration with ServiceNow for incident management and data synchronization. Once configured, specify the connector profile name in the variables for seamless integration.

## Deployment Process:
1. Configure ServiceNow connector in AppFlow.
2. Specify connector profile name in variables.
3. Utilize Terraform to deploy infrastructure modules in the following sequence:
   a. core_delta_lake
   b. glue_resources
   c. other_resources
   d. datashare_resources

