# Snowfall 2.0: Architecture, Infrastructure and Dataset Flow

## 1. Purpose

Snowfall 2.0 is the UK Snowfall data platform for ingesting, standardizing, transforming and serving operational and incident data across multiple enterprise sources. It is designed as an AWS-based lakehouse platform that combines Terraform-managed infrastructure, event-driven ingestion, AWS Glue transformation pipelines, Delta Lake storage and Athena query access.

This page documents:

- The Snowfall 2.0 platform architecture
- The infrastructure responsibilities by module
- The end-to-end data flow from source system to analytics output
- The main dataset families handled by the platform
- The orchestration and operational logic behind the pipelines

## 2. Snowfall 2.0 Overview

Snowfall 2.0 is organized into four Terraform modules that work together as one platform:

| Module | Responsibility |
| --- | --- |
| `core_delta_lake` | Base platform infrastructure: S3, Lambda, AppFlow, APIs, SNS, WebSocket components |
| `glue_resources` | Transformation runtime: Glue jobs, workflow definitions, script packaging, Glue catalog databases |
| `other_resources` | Event-driven orchestration: EventBridge rules that connect raw data arrival to workflow execution |
| `datashare_resources` | Datashare distribution layer: datashare S3 buckets, transfer Lambdas and EventBridge wiring for downstream sharing |

The deployment order is:

1. `core_delta_lake`
2. `glue_resources`
3. `other_resources`
4. `datashare_resources`

This order matters because later modules consume outputs from earlier modules using Terraform remote state.

## 3. High-Level Architecture

Snowfall 2.0 follows this processing model:

`Source Systems -> Landing S3 -> Landing Trigger Lambda -> Raw S3 -> EventBridge -> Glue Workflow -> Preparation Delta -> Processed Delta -> Semantic Delta -> Athena`

Snowfall 2.0 also includes a datashare branch for curated downstream distribution:

`Core Processed / External Datashare Feeds -> Datashare Lambdas -> Datashare Landing / Datashare Processed / Tech360 Buckets`

At a high level:

- External systems land files or API outputs into the landing bucket
- A routing Lambda classifies and moves data into the correct raw path
- Raw object creation events trigger dataset-specific Glue workflows
- Glue pipelines standardize and enrich the data through layered transformations
- Semantic outputs are published for reporting and Athena consumption

## 4. Snowfall 2.0 Infrastructure Layers

### 4.1 Core Platform Layer

The `core_delta_lake` module provisions the platform foundation:

- S3 buckets for landing, raw, preparation, processed, semantic, artifact and temporary paths
- Lambda functions for ingestion, routing, API integrations and operational services
- AppFlow provisioning hooks for ServiceNow extraction
- REST API and JWT authorizer components for service agent uploads
- WebSocket API resources for Snowfall proactive/healing features
- SNS topics for operational notifications

The module wiring is centralized in `terraform/core_delta_lake/main.tf`.

### 4.2 Transformation Layer

The `glue_resources` module provisions the transformation engine:

- One reusable Glue job runner
- Dataset-specific workflows and triggers
- Glue databases for `preparation`, `processed`, `semantic` and `microstrategy`
- Packaged pipeline code and shared Python utilities

The important design choice is that Snowfall 2.0 uses one main Glue runner that dynamically loads the dataset-specific pipeline class at runtime.

### 4.3 Orchestration Layer

The `other_resources` module binds S3 raw object creation events to Glue workflows using EventBridge rules. This keeps ingestion and transformation loosely coupled and allows each dataset family to be triggered independently.

### 4.4 Datashare Layer

The `datashare_resources` module provisions the Snowfall 2.0 datashare distribution estate:

- A datashare landing bucket for externally shared inbound datasets
- A datashare processed bucket for curated outbound copies from Snowfall processed data
- A dedicated Tech360 bucket for selected datashare outputs
- Lambda functions to move and synchronize data into datashare destinations
- EventBridge configuration for both scheduled sync and processed-bucket event-driven replication

This module acts as a publishing and exchange layer rather than a transformation engine.

## 5. Storage Model and Data Zones

Snowfall 2.0 uses a layered lakehouse design.

| Layer | Purpose | Typical Content |
| --- | --- | --- |
| Landing | Initial ingestion zone | Raw files from AppFlow, Lambda collectors, APIs |
| Raw | Standardized source routing zone | Files classified by dataset family and source path |
| Preparation | Cleansed and validated Delta tables | Deduplicated, quality-checked, PII-masked data |
| Processed | Business-ready Delta tables | Split JSON fields, typed timestamps, enriched joins |
| Semantic | Reporting-ready Delta tables | Aggregated business outputs and reporting views |
| Artifact | Code and SQL assets | Glue scripts, libraries, Athena views |
| Datashare Landing | External datashare ingress zone | NCR, Genesys, GCC, HappySignals and other shareable inbound feeds |
| Datashare Processed | Datashare export zone | Curated copies of selected processed datasets |
| Datashare Tech360 | Targeted downstream delivery zone | Tech360-facing shared folders |

### 5.1 Why this layering exists

Each layer has a clear responsibility:

- Landing isolates upstream ingestion from downstream logic
- Raw normalizes source routing without imposing business transformation yet
- Preparation focuses on quality and technical standardization
- Processed introduces business enrichment and curated schemas
- Semantic creates report-ready analytical outputs

## 6. Ingestion Patterns in Snowfall 2.0

Snowfall 2.0 ingests data through multiple patterns.

### 6.1 AppFlow-based ingestion

Used primarily for ServiceNow and similar SaaS-origin data.

Behavior:

- AppFlow connector must already exist before deployment
- Terraform triggers local Python provisioning for flow creation
- AppFlow lands files into source-specific folders in the landing bucket

Typical examples:

- UK ServiceNow incident daily and intraday
- UK ServiceNow location, service request, service offering, sys user, sys user group
- NCR ServiceNow families

### 6.2 Scheduled Lambda ingestion

Used for API-driven sources such as Meraki and New Relic.

Behavior:

- EventBridge schedules invoke dedicated Lambda functions
- Lambdas fetch data from external APIs
- Results are written into landing bucket source paths

Typical examples:

- Meraki device info
- Meraki client info
- New Relic device info
- New Relic network info
- New Relic device metrics
- New Relic process info
- New Relic digital FOE and 3PO response feeds

### 6.3 API and agent-based ingestion

Snowfall 2.0 also exposes API-driven ingress paths for operational use cases:

- Service agent upload API protected by JWT authorizer
- WebSocket API for proactive/healing workflows
- ThousandEyes alert API path

These flows extend Snowfall beyond pure batch ingestion into operational event handling.

### 6.4 Datashare ingestion and distribution

Snowfall 2.0 also supports datashare-specific movement outside the primary landing/raw/preparation/processed path.

There are two main datashare patterns:

- Scheduled landing synchronization from datashare landing into Snowfall or Tech360 targets
- Event-driven replication from Snowfall processed into the datashare processed bucket

This makes datashare a controlled exchange layer for selected datasets rather than part of the standard Glue transformation chain.

## 7. Landing to Raw Flow

The landing bucket is not intended as the long-term processing source. Its purpose is controlled ingress.

The landing trigger Lambda performs the landing-to-raw promotion.

### 7.1 Logic performed by the landing trigger

- Read object-created event from landing bucket
- Load dataset mapping rules from `mapping.json`
- Determine the correct raw destination path for the incoming object
- Apply special handling for Amazon Connect data
- Copy the object into the correct raw path
- Delete the original landing object

### 7.2 Error handling

If the landing trigger fails:

- The object is copied to an `error/` path
- The original object is removed from landing
- An SNS notification is sent

This makes the landing Lambda the first quality gate in Snowfall 2.0.

## 8. Raw to Glue Workflow Orchestration

Snowfall 2.0 treats the raw bucket as the event boundary for transformation.

When a new object lands in a raw prefix:

- EventBridge matches the object path pattern
- The matching Glue workflow trigger is invoked
- Workflow properties identify the `GROUP` and `DATASET`
- The main Glue runner dynamically loads the correct pipeline class

This design avoids one Glue job per dataset and instead reuses one execution framework with many dataset-specific classes.

## 8.1 Datashare orchestration model

Datashare orchestration is separate from the Glue workflow path.

It uses:

- A scheduled datashare landing trigger Lambda, running at 30 minutes past each hour
- A processed-copy trigger Lambda, running every 5 minutes
- EventBridge notifications on the core processed bucket for selected prefixes

The datashare path therefore operates as a parallel delivery and sharing mechanism alongside the main Snowfall processing model.

## 9. Glue Processing Pattern in Snowfall 2.0

### 9.1 Main runner behavior

The main Glue runner:

- Reads workflow properties or job arguments
- Determines `GROUP`, `DATASET`, `SUB_DATASET` and optional `EXTENSION`
- Dynamically imports the matching pipeline class
- Executes `process_flow()` for that class

### 9.2 Standard transformation contract

Each pipeline inherits from a shared base class and follows the same contract:

- `get_data()`
- `transform_data(df)`
- `save_data(df)`

The common base class provides shared capabilities such as:

- Reading from S3
- Delta merge behavior
- Athena table creation
- Data quality rule execution
- SNS error handling
- Schema and partition management
- Movement of failed records to error paths

### 9.3 Transformation stages

Snowfall 2.0 typically performs the following transformations in sequence:

1. Remove duplicate records
2. Convert nested structures into stable forms
3. Trim and standardize values
4. Run dataset-specific data quality rules
5. Mask PII where configured
6. Derive unique row set logic
7. Add CDC and lineage columns
8. Add partition columns
9. Save as Delta and register or update Athena metadata

## 10. Dataset Catalog in Snowfall 2.0

Below is the main dataset landscape grouped by domain.

### 10.1 UK ServiceNow datasets

| Dataset | Ingestion Method | Raw Path | Processing Mode |
| --- | --- | --- | --- |
| Change Request | AppFlow | `service_now/change_request/` | Event-driven |
| Incident Daily | AppFlow | `service_now/incident/daily/` | Event-driven |
| Incident Intraday | AppFlow | `service_now/incident/intraday/` | Event-driven |
| Location | AppFlow | `service_now/location/` | Event-driven |
| Problem Record | AppFlow | `service_now/problem_record/` | Event-driven |
| Service Offering | AppFlow | `service_now/service_offering/` | Event-driven |
| Service Request | AppFlow | `service_now/service_request/` | Event-driven |
| Sys User | AppFlow | `service_now/sys_user/` | Event-driven |
| Sys User Group | AppFlow | `service_now/sys_user_group/` | Event-driven |

### 10.2 NCR ServiceNow datasets

| Dataset Family | Landing/Raw Domain |
| --- | --- |
| Change Request | `ncr_service_now/change_request/` |
| Incident | `ncr_service_now/incident/` |
| Incident SLA | `ncr_service_now/incident_sla/` |
| Incident Task | `ncr_service_now/incident_task/` |
| Problem Record | `ncr_service_now/problem_record/` |
| Problem Task | `ncr_service_now/problem_task/` |
| Service Case | `ncr_service_now/service_case/` |
| Knowledge Base | `ncr_service_now/knowledge_base/` |
| Knowledge | `ncr_service_now/knowledge/` |
| Knowledge Feedback | `ncr_service_now/knowledge_feedback/` |
| Knowledge Use | `ncr_service_now/knowledge_use/` |
| Worknotes | `ncr_service_now/worknotes/` |

### 10.3 ODS datasets

| Dataset | Raw Path |
| --- | --- |
| Trading Hours | `ods/trading_hours/` |
| Adjusted Trading Hours | `ods/adj_trading_hours/` |
| Location Hierarchy | `ods/location_hierarchy/` |
| User Data | `ods/user_data/` |

### 10.4 Meraki datasets

| Dataset | Ingestion Pattern | Raw Path |
| --- | --- | --- |
| Device Info | Scheduled Lambda | `meraki/device_info/` |
| Client Info | Scheduled Lambda | `meraki/client_info/` |

### 10.5 New Relic datasets

| Dataset | Ingestion Pattern | Raw Path |
| --- | --- | --- |
| RMP Device Info | Scheduled Lambda | `newrelic/newrelic_rmp_device_info/` |
| RMP Network Info | Scheduled Lambda | `newrelic/newrelic_rmp_network_info/` |
| RMP Network Daily Aggregate | Scheduled Lambda | `newrelic/newrelic_rmp_network_info_daily_aggregate/` |
| RMP Device Metrics | Scheduled Lambda | `newrelic/newrelic_rmp_device_metrics/` |
| RMP Process Info | Scheduled Lambda | `newrelic/newrelic_rmp_process_info/` |
| Digital GMA FOE Response | Scheduled Lambda | `newrelic/newrelic_digital_gma_foe_response/` |
| Digital 3PO FOE Response | Scheduled Lambda | `newrelic/newrelic_digital_3po_foe_response/` |

### 10.6 Additional platform datasets

| Dataset Family | Raw/Landing Domain |
| --- | --- |
| Amazon Connect | `amazon_connect/` |
| Restaurant Config | `restaurant_config/` |
| Genesys Contact Center Settings | `genesys/contact_center_settings/` |
| Genesys Conversation Attributes | `genesys/conversation_attributes/` |
| Genesys Conversations Detail | `genesys/conversations_detail/` |
| Genesys Conversations | `genesys/conversations/` |
| Genesys Primary Presence | `genesys/primary_presence/` |
| Genesys Queue Abandons | `genesys/queue_abandons/` |
| Genesys Queue Configuration | `genesys/queue_configuration/` |
| Genesys Routing Status | `genesys/routing_status/` |
| Genesys Queue Interval History | `genesys/queue_interval_history/` |
| Genesys Session Summary | `genesys/session_summary/` |
| Genesys User Details | `genesys/user_details/` |
| Genesys User Status Interval History | `genesys/user_status_interval_history/` |
| Google Contact Center | `gcc/` |
| HappySignals | `happysignals/` |

### 10.7 Datashare landing datasets

The datashare landing bucket contains externally shared or exchange-oriented source paths such as:

| Dataset Family | Datashare Landing Path |
| --- | --- |
| NCR Change Request | `ncr_service_now/change_request/` |
| NCR Incident | `ncr_service_now/incident/` |
| NCR Problem Record | `ncr_service_now/problem_record/` |
| NCR Service Case | `ncr_service_now/service_case/` |
| NCR Incident Task | `ncr_service_now/incident_task/` |
| NCR Incident SLA | `ncr_service_now/incident_sla/` |
| NCR Problem Task | `ncr_service_now/problem_task/` |
| NCR Knowledge Base | `ncr_service_now/knowledge_base/` |
| NCR Knowledge | `ncr_service_now/knowledge/` |
| NCR Knowledge Feedback | `ncr_service_now/knowledge_feedback/` |
| NCR Knowledge Use | `ncr_service_now/knowledge_use/` |
| NCR Worknotes | `ncr_service_now/worknotes/` |
| NCR Account | `ncr_service_now/account/` |
| Genesys Families | `genesys/...` |
| Google Contact Center | `gcc/` |
| HappySignals | `happysignals/` |

### 10.8 Datashare processed export datasets

The datashare processed bucket is used for selective replication of curated data from the main Snowfall processed layer.

Configured export domains include:

| Dataset Family | Datashare Processed Path |
| --- | --- |
| Trading Hours | `ods/trading_hours/` |
| Location Hierarchy | `ods/location_hierarchy/` |
| Adjusted Trading Hours | `ods/adj_trading_hours/` |
| Meraki | `meraki/` |
| New Relic | `newrelic/` |
| ODS User Data | `ods_user_data/` |

## 11. Example End-to-End Dataset Flow: Incident Daily

The UK ServiceNow Incident Daily path is a strong example of the Snowfall 2.0 data model.

### 11.1 Ingestion

- Source system: ServiceNow
- Ingestion type: AppFlow
- Landing path: ServiceNow-specific landing folder
- Raw path after routing: `service_now/incident/daily/`

### 11.2 Preparation stage

Preparation pipeline responsibilities include:

- Duplicate removal
- Struct-to-string normalization
- Whitespace cleanup
- Data quality validation
- PII masking
- SQL-based latest-row uniqueness logic
- CDC column creation
- Partition creation using `sys_created_on`

Output:

- Delta Lake table in preparation bucket
- Athena registration for preparation-layer incident dataset

### 11.3 Processed stage

Processed pipeline responsibilities include:

- Expanding JSON attributes into structured columns
- Converting duration-style fields to seconds
- Splitting and typing timestamps
- Enriching with location data
- Filtering rows that passed data quality
- Producing a curated processed schema

Output:

- Curated Delta table in processed bucket

### 11.4 Semantic stage

Semantic daily incident logic produces a reporting-friendly daily snapshot by:

- Evaluating the reporting date
- Selecting relevant current and historical incident rows
- Ranking by latest update time
- Calculating end-of-day incident status logic
- Publishing a semantic dataset partitioned by reporting date

Output:

- Semantic Delta dataset for reporting and Athena querying

## 12. Workflow Types in Snowfall 2.0

Snowfall 2.0 uses two main workflow styles.

### 12.1 Event-driven workflows

These are triggered by raw bucket arrivals.

Examples:

- `incident_daily`
- `incident_intraday`
- `location`
- `problem_record`
- `service_offering`
- `service_request`
- `sys_user`
- `sys_user_group`
- `trading_hours`
- `adj_trading_hours`
- `meraki_device_info`
- `meraki_client_info`
- `newrelic_rmp_*`

### 12.2 Scheduled semantic workflows

These run on schedule, typically at `cron(0 3 * * ? *)`.

Examples:

- Semantic Amazon Connect
- Semantic franchisee incidents
- Semantic daily incidents

This separation allows Snowfall 2.0 to handle both near-real-time ingestion and scheduled reporting views.

## 12.1 Datashare transfer types

Datashare uses transfer-oriented workflows rather than Glue workflows.

### Scheduled datashare transfers

- Datashare landing trigger runs hourly at 30 minutes past the hour
- Used to move datashare landing content into Snowfall landing or Tech360 targets

### Event-driven datashare replication

- EventBridge listens to selected object creation events in the core processed bucket
- Matching prefixes invoke the datashare processed trigger Lambda
- That Lambda copies selected datasets into the datashare processed bucket

This gives Snowfall 2.0 a controlled export channel for downstream consumers.

## 13. Data Quality and Governance

Snowfall 2.0 applies governance in the transformation layer rather than leaving quality to downstream consumers.

### 13.1 Data quality checks

The framework evaluates:

- Row count expectations
- Column count expectations
- Mandatory key completeness
- Dataset-specific quality rules

If all records fail, the pipeline raises an exception.

If only some records fail:

- Failed rows are written to an error path
- SNS alerts can be triggered
- Successful rows continue through the pipeline

### 13.2 PII handling

PII redaction is configured per dataset. For example, incident-family datasets redact fields such as notes, descriptions and comments before downstream use.

### 13.3 Error paths

Snowfall 2.0 preserves error traceability by moving bad records or source files into error folders instead of silently dropping them.

## 14. Delta Lake and Athena Strategy

Snowfall 2.0 uses Delta Lake as the storage format for transformed layers and Athena as the query surface.

Pattern:

- If a Delta table does not yet exist, the pipeline creates it and triggers Athena table creation
- If the Delta table exists, the pipeline merges or rewrites according to dataset logic
- Athena metadata is updated as needed for semantic consumption

This pattern gives the platform transactional-like table behavior in S3 while still exposing query access through Athena.

## 15. Operational Logic and Design Conventions

Snowfall 2.0 follows a few strong conventions:

- Infrastructure is fully Terraform-managed where possible
- AppFlow connector prerequisites are externalized and must exist before deployment
- Raw bucket object creation is the main trigger contract for transformations
- One Glue runner executes many pipelines through dynamic imports
- Preparation is for technical standardization
- Processed is for business curation
- Semantic is for reporting and downstream analytics
- Datashare is for controlled distribution and sharing of selected datasets
- SNS is used for operational notification on failures

## 16. Snowfall 2.0 Deployment Summary

### 16.1 Prerequisites

- ServiceNow AppFlow connector must exist
- Terraform backend bucket and environment variables must be configured
- Deployment role must have permissions for S3, Lambda, Glue, Athena, SNS, EventBridge and AppFlow-related actions

### 16.2 Deployment sequence

1. Deploy `core_delta_lake`
2. Deploy `glue_resources`
3. Deploy `other_resources`
4. Deploy `datashare_resources`

### 16.3 Why the order matters

- Core creates the buckets, Lambdas, SNS topics and other shared resources
- Glue depends on core outputs for paths and topic references
- EventBridge depends on both core bucket names and Glue workflow trigger ARNs
- Datashare depends on core processed outputs, datashare bucket creation and datashare transfer Lambdas

## 17. Recommended Confluence Labels

- `snowfall`
- `snowfall-2.0`
- `aws`
- `data-platform`
- `lakehouse`
- `glue`
- `service-now`
- `architecture`

## 18. Suggested Short Description for Confluence

Snowfall 2.0 is the UK Snowfall AWS lakehouse platform for ingesting, transforming and serving ServiceNow, Meraki, New Relic, ODS, Amazon Connect and related operational datasets through an event-driven, Delta Lake-based architecture.

## 19. Key Takeaways

- Snowfall 2.0 is an event-driven AWS data platform
- The platform separates infrastructure, transformation and orchestration cleanly
- Data flows from landing to raw to preparation to processed to semantic
- Datashare extends the platform with a dedicated sharing and downstream distribution path
- Glue is driven by reusable framework logic with dataset-specific classes
- Governance is built into the pipelines through DQ, PII handling and error routing
- The system supports both ingestion analytics and operational integration use cases