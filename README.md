# Snowfall Data Pipeline

This repository contains all the necessary Infrastructure as Code (IaC) to build and manage the Snowfall data pipeline. The pipeline is designed to handle the following datasets:

| Data item    | Item Description                     |
|--------------|--------------------------------------|
| 1            | incidents-daily                      |
| 2            | incidents-intraday                   |
| 3            | amazon-connect                       |
| 4            | change-request                       |
| 5            | location                             |
| 6            | location-hierarchy                   |
| 7            | location-hierarchy-adj-trading-hours |
| 8            | location-hierarchy-trading-hours     |
| 9            | problem-request                      |
| 10           | service-offering                     |
| 11           | service-request                      |
| 12           | sys-user                             |
| 13           | sys-user-group                       |

## Infrastructure as Code (IaC)

### Terraform

- **`/terraform/`**: This directory contains Terraform configurations for provisioning the necessary infrastructure components.

    - `main.tf`: defines and loads the modules defined in resources

    - `variables.tf`: key environment variables that will allow deployment to the relavent account

    - `development.tfvars`: values for running from the command line

    - `resources`: 5 modules have been defined for building the required resources for

| Resource item | Item Description                   |
|---------------|------------------------------------|
| 1             | s3                                 |
| 2             | glue, shared scripts and workflows |
| 3             | event bridge                       |
| 4             | sns                                |




### AWS Glue Scripts

- **`/glue-scripts/`**: Here you'll find AWS Glue scripts for data transformation and ETL processes.

    - `aws_utilities.py`: collection of functions designed to streamline and orchestrate various data-related tasks within the AWS ecosystem

    - `script_config.py`: structured set of parameters and settings used to drive the orchestration of the workflows.
 
    - `transform.py`: key transformations on raw or source data.
 
    - `main.py`: main script to run the pipeline.
 

## Getting Started (WIP)

To deploy the Snowfall data pipeline using Terraform, follow these steps:

1. Clone this repository:

    ```bash
    git clone https://github.com/your-username/snowfall-data-pipeline.git
    ```

2. Navigate to the Terraform directory:

    ```bash
    cd snowfall-data-pipeline/terraform
    ```

3. Initialize Terraform:

    ```bash
    terraform init
    ```

4. Apply the Terraform configurations:

    ```bash
    terraform apply
    ```

5. Execute the Glue scripts in the AWS Glue console or using the AWS CLI.

---

