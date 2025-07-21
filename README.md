# Churn Prediction Model Evaluation Pipeline

* TODO

# Infrastructure Diagram

* TODO

# "Non-Production Use" Disclaimer

* TODO

# Prerequisites

* AWS Account
    * AWS Account required to run the pipeline to the cloud as a user
    * AWS Account NOT required to run unit and integration tests
* AWS User with the following Permissions:
    * TBD
* AWS CLI installed with `aws configure` run to store credentials locally
* Docker installed and Docker Engine running
* Pip and Pipenv installed
* Terraform installed

# Docker Local Image Storage Space Requirements

 About 1.8GB of disk space is required to store the following Docker images locally before deploying to AWS Elastic Container Repositories (ECR):
* **Custom Grafana Image**
    * Packages database configuration and dashboard files
    * Uses Grafana `grafana/grafana-enterprise:12.0.2-security-01` image
* **S3-to-Prefect Lambda Function**
    * Invokes orchestration flow when new files are dropped into S3
    * Uses AWS

# Steps to Run Pipeline

1.  Install prerequisites (see list above)
1.  Create an S3 bucket to store the state of your Terraform infrastructure (e.g. `mlops-churn-pipeline-tf-state-<some random number>`)
1.  Clone `mlops-churn-pipeline` repository locally
1.  Edit root Terraform configuration to store state within S3
    1.  Edit `mlops-churn-pipeline/infrastructure/main.tf`
    1.  Change `terraform.backend.s3.bucket` to the name of the bucket you created
    1.  Change `terraform.backend.s3.region` to your AWS region
1.  Copy Terraform `stg.template.tfvars` file to new `stg.tfvars` file and define values for each key within:
| **Key Name** | **Purpose** | **Example Value** |
| ------------ | ----------- | ----------------- |
| `project_id` | Used as name for many AWS resources created by Terraform to avoid naming collisions, including the S3 bucket while files will be dropped and generated.  Choose something unique to avoid S3 bucket naming collisions. | `mlops-churn-pipeline-1349094` |
| `vpc_id` | Your AWS VPC ID | `vpc-0a1b2c3d4e5f6g7h8` |
| `aws_region` | Your AWS Region | `us-east-2` |
| `db_username` | Username for Postgres database used to store MLflow, Prefect, and Evidently Metrics.  Must conform to Postgres rules (e.g. lowercase, numbers, underscores only) | `my_super_secure_db_name` |
| `db_password` | Password for Postgres database. Use best practices and avoid spaces. | `Th1s1sAStr0ng#Pwd!` |
| `grafana_admin_user` | Username for Grafana account used to **edit** data drift and model prediction scores over time.  | `grafana_FTW` |
| `grafana_admin_password` | Password for Grafana account | `Grafana4Lyfe!123` |
| `grafana_anon_org_name` |
| `subnet_ids`  |
| `my_ip` |
| `my_email_address` |
1.  `cd {REPO_HOME}/code/orchestration` then `pipenv shell`
1.  Run `make plan` and review the infrastructure to be created (see diagram above for summary)
1.  Run `make apply` to build Terraform infrastructure, set Prefect Secrets, update GitHub Actions workflow, and start ECS services
1.  Click each of the 4 ECS Service URLs to confirm they are running: MLFlow, Prefect Server, Evidently, Grafana
1.  ` cd {REPO_HOME}` then `make model-registry` to train `XGBoostChurnModel` churn model and upload to MLFlow model registry with `staging` alias.
    1.  Confirm it was created by visiting the Model Registry with the MLFlow UI
1.  Deploy the `churn_prediction_pipeline` Prefect Flow to your Prefect Server using GitHub Actions
    1. Commit your cloned repo (including `{REPO_HOME}/.github/workflows/deploy-prefect.yml` updated with generated `PREFECT_API_URL`)
    1. Log in your GitHub account, access your committed repo project and create the following Repository Secrets (used by `deploy-prefect.yml`):
        1.  `AWS_ACCOUNT_ID`
        1.  `AWS_ACCESS_KEY_ID`
        1.  `AWS_SECRET_ACCESS_KEY`
        1.  `AWS_REGION`
    1.  Nagivate to GitHub Project Actions tab, select the workflow `Build and Deploy Prefect Flow to ECR`, and verify it completes successfully.
