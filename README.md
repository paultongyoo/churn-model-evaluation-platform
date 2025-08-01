# Churn Model Evaluation Platform

(For those evaluating this project for [DataTalks.club MLOps Zoomcamp Certification ↗](https://datatalks.club/blog/mlops-zoomcamp.html), see the [**"DataTalks.club MLOps Zoomcamp Evaluation Criteria" section**](#datatalksclub-mlops-zoomcamp-evaluation-criteria) for mappings between this document's sections and each criteria.)

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Key Features](#key-features)
3. [Customer Churn Data Source](#customer-churn-data-source)
4. [Platform Processes](#platform-processes)
   - [Model Training and Registry Deployment](#model-training-and-registry-deployment)
   - [Model Inference, Reporting, and Evaluation](#model-inference-reporting-and-evaluation)
5. [Platform Infrastructure Diagram](#platform-infrastructure-diagram)
6. [S3 File Drop Folder Structure](#s3-file-drop-folder-structure)
7. [Project Folders & Files](#project-folders--files)
8. [Security Limitations & Future Improvements](#security-limitations--future-improvements)
9. [Installation Prerequisites](#installation-prerequisites)
10. [Docker Local Image Storage Space Requirements](#docker-local-image-storage-space-requirements)
11. [Library Dependencies & Version Numbers](#library-dependencies--version-numbers)
12. [How to Install Platform](#how-to-install-platform)
13. [Platform ECS Services](#platform-ecs-services)
    - [MLflow Tracking Server & Model Registry](#mlflow-tracking-server--model-registry)
    - [Optuna Hyperparameter Tuning Dashboard](#optuna-hyperparameter-tuning-dashboard)
    - [Prefect Orchestration Server and Worker Service](#prefect-orchestration-server-and-worker-service)
    - [Evidently Non-Time-Series Dashboard and Reports UI](#evidently-non-time-series-dashboard-and-reports-ui)
    - [Grafana Time-Series Dashboard UI](#grafana-time-series-dashboard-ui)
14. [How to Upload Data](#how-to-upload-data)
15. [How to Evaluate Data Drift & Model](#how-to-evaluate-data-drift--model)
16. [Data Drift & Prediction Score Email Alerts](#data-drift--prediction-score-email-alerts)
17. [Unit Test Examples](#unit-test-examples)
18. [Integration Test Examples](#integration-test-examples)
19. [Pre-Commit Hooks](#pre-commit-hooks)
    - [How to Activate Pre-Commit Hooks](#how-to-activate-pre-commit-hooks)
    - [Hooks List](#hooks-list)
21. [Makefile Targets](#makefile-targets)
22. [CI-CD Implementation](#ci-cd-implementation)
23. [DataTalks.club MLOps Zoomcamp Evaluation Criteria](#datatalksclub-mlops-zoomcamp-evaluation-criteria)


## Problem Statement

* Companies rely on churn prediction models to proactively retain valuable customers--an effort that is typically more cost-effective than acquiring new ones.
* However, once deployed, these models risk losing accuracy over time as customer behavior and demographics shift.
* This project addresses this challenge by providing Data Scientists, Machine Learning Engineers, and their stakeholders a platform to continuously train, deploy, and monitor churn models, enabling organizations to detect drift, maintain model quality, and adapt to changing customer dynamics.

## Key Features
| Area | Features |
| ---- | -------- |
| 🧠 **Model Development** | <ul><li>[Jupyter Notebook ↗](https://jupyter.org/) provides a data scientist-friendly environment for exploratory data analysis and feature engineering.</li><li>Training logic extracted into a reusable module, ensuring consistency between training and inference.</li><li>Fast experimentation enabled via [Optuna ↗](https://optuna.org/) for Bayesian optimization and [MLflow ↗](https://mlflow.org/) for experiment tracking.</li><li>Developer-friendly codebase includes unit/integration tests, [GitHub Actions-based CI/CD ↗](https://github.com/features/actions), and pre-commit hooks for linting and formatting.</li></ul> |
| 📊 **Model Evaluation** | <ul><li>Evaluates model on both training and holdout datasets to establish baseline bias and variance for future improvement.</li><li>MLflow UI enables deep comparison of experiment runs, visualizations (confusion matricies, precision-recall curves), and SHAP explanatory plots.</li></ul> |
| 🚀 **Model Deployment** | <ul><li>Each model version is packaged in the [MLflow Model Registry ↗](https://mlflow.org/docs/latest/ml/model-registry/) with metadata, dependencies, and signatures for reproducibility.</li><li>Alias-based promotion supports decoupling development from deployment.</li><li>Deployment to [AWS ECS ↗](https://aws.amazon.com/ecs/) via [Prefect ↗](https://www.prefect.io/) provides scalable and observable on-demand inference.</li></ul> |
| 📈 **Model Monitoring** | <ul><li>[Evidently.ai ↗](https://www.evidentlyai.com/) generates automated reports for data drift and prediction performance after each inference run.</li><li>Pre-built [Grafana ↗](https://grafana.com/grafana/) dashboard visualizes model metrics over time, helping distinguish anomalies from signals indicating the need for model development.</li></ul> |
| 🔁 **Model Maintenance** | <ul><li>Email alerts triggered if data drift exceeds threshold or model prediction scores (F1, precision, recall, accuracy) fall below acceptable limits.</li><li>Enables manual model retraining and defines a framework extensible to automated retraining pipelines.</li></ul> |

## Customer Churn Data Source

* The labeled customer churn data used to train the model was randomly collected from an Iranian telecom company on 4/8/2020 and made available for download by the [UC Irvine Machine Learning Repository ↗](https://archive.ics.uci.edu/dataset/563/iranian+churn+dataset).
* This repository contains a `data/` folder with several CSV files prefixed with `customer_churn_*`.
* The following files were split from the original Iranian Telecom dataset:
   * `customer_churn_0.csv` (used as training set)
   * `customer_churn_1.csv`
   * `customer_churn_2.csv`
* The `customer_churn_synthetic_*.csv` files were generated by [Gretel.ai ↗](https://www.gretel.ai) using the original dataset as input.

## Platform Processes

Two independent processes were enabled by this project, joined by the MLflow Model Registry:

### Model Training and Registry Deployment

The following process is implemented with two files inside the `code/orchestration/modeling/` folder:
* **Jupyter Notebook:** `churn_model_training.ipynb`
	* Main location for EDA, hyperparameter tuning, and calling upon the `modeling.churn_model_training` module below
* **Python Module:** `churn_model_training.py`
	* Contains functions used in both Jupyter Notebook and in Prefect Flow `churn_prediction_pipeline.py` (see [Model Inference, Reporting, and Evaluation](#model-inference-reporting-and-evaluation) section below)

```mermaid
flowchart TD
    A[Download training data]
    B[Prepare data]
    C[Tune hyperparameters]
    D[Narrow parameter search space using Optuna UI]
    E[Train model]
    F[Evaluate model on training set using MLflow UI]
    G[Evaluate model on holdout set using MLflow UI]
    H[Is model performance sufficient?]
    I[Promote model in MLflow Registry]
    A --> B --> C --> E --> F --> G --> H;
    C --> D --> C;
    H --> |Yes| I;
    H --> |No| B;
```

### Model Inference, Reporting, and Evaluation

* The following process is orchestrated by the Prefect Flow `code/orchestration/churn_prediction_pipeline.py`.
* A new flow run is created for each file dropped into the S3 File Drop Folder `input` folder (see [S3 File Drop Folder Structure](#s3-file-drop-folder-structure)).

```mermaid
flowchart TD
    A[Drop new customer<br/>churn data into S3]
    B[Load latest promoted model in MLflow Registry]
    C[Validate file input]
    D[Prepare data, reusing training logic]
    E[Generate predictions]
    F[Append predictions to file input]
    G[Generate Evidently data drift and prediction performance report]
    H[Save report to database]
    I[Did drift exceed threshold?]
    J[Send drift email alert]
    K[Did prediction performance drop below threshold?]
    L[Send prediction score email alert]
    M[Evaluate detailed drift and performance report in Evidently UI]
    N[Evaluate drift and performance over time in Grafana UI]
    A-->B-->C-->D-->E-->F-->G-->H-->I-->K-->M-->N;
    I--> |Yes| J;
    K--> |Yes| L;
```

## Platform Infrastructure Diagram
(click to enlarge)

![MLOps Churn Platform Infrastructure Diagram](readme-assets/mlops_churn_platform_infrastructure_diagram_paultongyoo.jpg)

## S3 File Drop Folder Structure

<pre>
s3://your_project_id
└── data
    ├── input        # Customer churn files uploaded here
    ├── processing   # Files moved here during processing
    ├── logs         # Log file created for each dropped file
    ├── processed    # Files moved here on successful processing
    └── errored      # Files moved here if error occurred during processing
</pre>

## Project Folders & Files

This project consists mainly of the following folders and files:
| Folder/File | Purpose |
|-------------|---------|
| `code/grafana/` | <ul><li>Contains Dockerfile that packages Grafana Enterprise image with:<ul><li>`grafana-postgres-datasource.yml`: Postgres Data Source configuration</li><li>`churn-model-evaluation.json`: Pre-created Data Drift and Prediction Score Evaluation Dashboard</li></ul></li></ul> |
| `code/orchestration/` | <ul><li>Contains Dockerfile that packages Prefect Flow pipeline consisting of:<ul><li>`churn_prediction_pipeline.py`: Contains main Prefect flow and tasks</li><li>`modeling/`<ul><li>Contains model training and registry deployment logic:<ul><li>`churn_model_training.ipynb` for model EDA, hyperparameter tuning, and model training</li><li>`churn_model_training.py` for extracting training logic to reuse in Prefect pipeline</li></ul></li></ul></li><li>`tests/`<ul><li>`unit/`<ul><li>Contains unit tests using `unittest.MagicMock` to mock all dependencies</li></ul></li><li>`integration/`<ul><li>Contains integration tests utilizing [`testcontainers.localstack` module ↗](https://testcontainers-python.readthedocs.io/en/latest/modules/localstack/README.html) to mock AWS component with [LocalStack ↗](https://www.localstack.cloud/) equivalent</li></ul></li></ul></li></ul></li></ul> |
| `code/s3_to_prefect_lambda/` | <ul><li>Contains Dockerfile that packages `lambda_function.py` and its dependencies for notifying Prefect pipeline of new file drops</li><li>Invoked by S3 Bucket Notification configured by Terraform `s3-to-prefect-lambda` module</li></ul> |
| `data/` | <ul><li>These files were split from the original data set:<ul><li>`customer_churn_0.csv`: File used to train the model</li><li>`customer_churn_1.csv`</li><li>`customer_churn_2_majority_drifted.csv`: File that exhibits data drift exceeding threshold (email notification will be sent)</li></ul></li><li>`customer_churn_synthetic_*.csv`: Generated using <a href="https://gretel.ai">Gretel.ai ↗</a></li></ul> |
| `infrastructure/` | <ul><li>Contains Infrastructure-as-Code (IaC) and scripts to configure or destroy 80+ AWS resources from single command<ul><li>`modules/`: Configures the following AWS Services:<ul><li>`alb/`: <a href="https://aws.amazon.com/elasticloadbalancing/application-load-balancer/">AWS Application Load Balancer ↗</a></li><li>`ecr/`: <a href="https://aws.amazon.com/ecr/">AWS Elastic Container Registry ↗</a></li><li>`ecs/`: <a href="https://aws.amazon.com/ecs/">AWS Elastic Container Service ↗</a></li><li>`rds-postgres/`: <a href="https://aws.amazon.com/rds/">AWS Relational Database Service ↗</a></li><li>`s3/`: <a href="https://aws.amazon.com/s3/">AWS Simple Storage Service ↗</a></li><li>`s3-to-prefect-lambda/`: <a href="https://aws.amazon.com/lambda/">AWS Lambda ↗</a></li><li>`sns/`: <a href="https://aws.amazon.com/sns/">AWS Simple Notification Service ↗</a></li></ul></li><li>`scripts/`<ul><li>`set-project-id.sh`: Adds the `project_id` you configured in `stg.tfvars` to the `.env` environment variable file.</li><li>`store_prefect_secrets.py`: Stores generated ALB endpoints and SNS topic ARN into Prefect Server for use by pipeline</li><li>`wait-for-services.sh`: Used to wait for <a href="#platform-ecs-services">Platform ECS Services</a> to become available via ALB before returning UI URLs to user</li></ul></li><li>`vars/`<ul><li>`stg.tfvars.template`: Base file for creating your own `stg.tfvars` (see [How to Install Platform](#how-to-install-platform))</li></ul></li></ul></li></ul> |
| `readme-assets/` | <ul><li>Screenshots for this readme</li></ul> |
| `.env` (generated) | <ul><li>Contains the following environment variables:<ul><li>Optuna DB Connection URL</li><li>MLflow, Optuna, Prefect, Evidently, and Grafana UI URLs</li><li>Prefect Server API URL</li><li>Your Project ID</li></ul></li></ul> |
| `.pre-commit-config.yaml` (generated) | Configures Pre-Commit hooks that execute prior to every commit (see [Pre-Commit Hooks](#pre-commit-hooks) section) 
| `Makefile` | <ul><li>Contains several targets to accelerate platform setup, development, and testing (see [Makefile Targets](#makefile-targets) section)</li></ul> |
| `upload_simulation_script.py` | <ul><li>Script that helps generate metrics over time for viewing in Grafana UI</li><li>Uploads the non-training data files into S3 File Drop Input folder 30 seconds apart</li></ul> |

### Full Project Folder Tree
The full project folder tree contents can be viewed [here](folder-structure.txt).

## Security Limitations & Future Improvements

| Security Limitation | Future Improvement |
| ------------------- | ------------------ |
| The IAM policy used is intentionally broad to reduce setup complexity. | Replace with least-privilege policies tailored to each service role.  |
| Public subnets are required to simplify RDS access from ECS and local machines. | Migrate to private subnets with NAT Gateway and use bastion or VPN access for local clients.  |
| The Prefect API ALB endpoint is publicly accessible to enable GitHub Actions deployment. | Restrict access to GitHub Actions IP ranges using ingress rules or CloudFront. |
| The MLflow ALB endpoint is publicly accessible to allow ECS Workers to reach the Model Registry.  | Limit access to internal ECS security groups only.  |
| The Prefect API ALB endpoint is visible in cleartext as an environment variable in the `.github/workflows/deploy-prefect.yml` file.  This may pose a security risk if your GitHub repo is publicly visible. | Consider migrating this variable to a GitHub Repository secret and automatically upserting this value as a new Terraform action post-`apply`. |

## Installation Prerequisites

* Python 3.10.x
* [AWS Account ↗](https://aws.amazon.com/)
    * AWS Account required to deploy the pipeline to the cloud and run it as a user
    * AWS Account NOT required to run unit and integration tests
* AWS User with the [Required IAM Permissions](#required-iam-permissions) policies
* [AWS CLI ↗](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html) installed with `aws configure` run to store AWS credentials locally
* [Docker ↗](https://docs.docker.com/get-started/get-docker/) installed and Docker Engine is running
* [Pip ↗](https://pip.pypa.io/en/stable/installation/) and [Pipenv ↗](https://pipenv.pypa.io/en/latest/)
* [Terraform ↗](https://developer.hashicorp.com/terraform/install)
* [Prefect ↗](https://docs.prefect.io/v3/get-started/install)
* [Pre-commit ↗](https://pre-commit.com/#install)
* GitHub Account
  * At this time, committing repo to your GitHub account and running GitHub Actions workflow is the only way to deploy Prefect flow to Prefect Server (without manual effort to circumvent)

### Required IAM Permissions

A user with the following AWS Managed Permissions policies was used when creating this Platform.  **Please note that this list is *overly-permissive* and may be updated in the future.**

* `AmazonEC2ContainerRegistryFullAccess`
* `AmazonEC2FullAccess`
* `AmazonECS_FullAccess`
* `AmazonRDSFullAccess`
* `AmazonS3FullAccess`
* `AmazonSNSFullAccess`
* `AmazonLambda_FullAccess`
* `CloudWatchLogsFullAccess`
* `IAMFullAccess`

## Docker Local Image Storage Space Requirements

The Docker images required for the following components occupy approximately 5.4 GB of local disk space:
* **Custom Grafana Bundle**
    * Packages database configuration and dashboard files with Grafana Enterprise
    * Uses Grafana `grafana/grafana-enterprise:12.0.2-security-01` image
* **S3-to-Prefect Lambda Function**
    * Invokes orchestration flow when new files are dropped into S3
    * Uses AWS `public.ecr.aws/lambda/python:3.12` image
* **Testcontainers + LocalStack**
	* Used by integration tests to mock AWS S3 service using LocalStack
 	* Uses LocalStack `localstack/localstack:4.7.0` image

After deployment, remove these local Docker images to conserve space.

## Library Dependencies & Version Numbers

See the `Pipfile` and `Pipfile.lock` files within the following folders for the full lists of library dependencies and version numbers used:

* `code/orchestration/`
* `code/s3_to_prefect_lambda/`

## How to Install Platform

1.  Install the [prerequisites](#installation-prerequisites)
2.  Ensure your Docker Engine is running
1.  Create an S3 bucket to store the state of your Terraform infrastructure (e.g. `churn-platform-tf-state-<some random number>`)
1.  Clone `churn-model-evaluation-platform` repository locally
1.  Edit root Terraform configuration to store state within S3
    1.  Edit file: `{REPO_DIR}/infrastructure/main.tf`
    1.  Change `terraform.backend.s3.bucket` to the name of the bucket you created
    1.  Change `terraform.backend.s3.region` to your AWS region
1.  Copy Terraform `infrastructure/vars/stg.template.tfvars` file to new `infrastructure/vars/stg.tfvars` file and define values for each key within:

| **Key Name** | **Purpose** | **Example Value** |
| ------------ | ----------- | ----------------- |
| `project_id` | Used as prefix for many AWS resources, including the S3 bucket while files will be dropped and generated.  **Must be a valid S3 name (e.g. unique, no underscores).  Must be 20 characters or less to prevent exceeding resource naming character limits.**   | `mlops-churn-pipeline` |
| `vpc_id` | Your AWS VPC ID | `vpc-0a1b2c3d4e5f6g7h8` |
| `aws_region` | Your AWS Region | `us-east-2` |
| `db_username` | Username for Postgres database used to store MLflow, Prefect, and Evidently Metrics.  Must conform to Postgres rules (e.g. lowercase, numbers, underscores only) | `my_super_secure_db_name` |
| `db_password` | Password for Postgres database. Use best practices and avoid spaces. | `Th1s1sAStr0ng#Pwd!` |
| `grafana_admin_user` | Username for Grafana account used to **edit** data drift and model prediction scores over time.  | `grafana_FTW` |
| `grafana_admin_password` | Password for Grafana account | `Grafana4Lyfe!123` |
| `subnet_ids`  | AWS Subnet IDs: **Must be *public* subnet IDs from *different Availability Zones* to allow Postgres RDS instance to be accessed by ECS services (and optionally your IP address)** | `["subnet-123abc456def78901", "subnet-234bcd567efg89012"]` |
| `my_ip` | IP address that will be granted access to Grafana UI, Optuna UI and Postgres DB | `203.0.113.42` |
| `my_email_address` | Email address that will be notified if input files exhibit data drift or prediction scores that exceed thresholds | `your.name@example.com` |

1.  `cd {REPO_DIR}/infrastructure` then `terraform init`.  If successful, this command will populate the Terraform State S3 bucket you created in Step 2 with the necessary files to capture the state of your infrastructure across Terraform command invocations.
2.  `cd {REPO_DIR}/code/orchestration` then `pipenv shell`
3.  `cd {REPO_DIR}`
1.  Run `make plan` and review the infrastructure to be created (see [Platform Infrastructure Diagram](#platform-infrastructure-diagram)
1.  Run `make apply` to build Terraform infrastructure, set Prefect Secrets, update GitHub Actions workflow YAML, and start ECS services.
    1.  After Terraform completes instantiating each ECS Service, it will execute the `wait_for_services.sh` script to poll the ALB URLs until each service instantiates its ECS Task and the service is ready for use.
    1.  For the user's convenience, each tool's URL is displayed to the user once ready for use (see [Platform ECS Services](#platform-ecs-services)).
1.  Click each of the 5 ECS Service URLs to confirm they are running: MLflow, Optuna, Prefect Server, Evidently, Grafana
1.  Run `make deploy-model` to train a `XGBoostChurnModel` churn model and upload it to the MLflow Model Registry with `staging` alias.
    1.  Confirm it was created and aliased by visiting the Model Registry within the MLflow UI
    2.  Note two versions of the model are visible in the registry evaluated using training and holdout datasets (`X_train` and `X_test`, respectively)
1.  Deploy the `churn_prediction_pipeline` Prefect Flow to your Prefect Server using GitHub Actions
    1. Commit your cloned repo (including `{REPO_DIR}/.github/workflows/deploy-prefect.yml` updated with generated `PREFECT_API_URL`)
    1. Log in to your GitHub account, navigate to your committed repo project and create the following [Repository Secrets ↗](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) (used by `deploy-prefect.yml`):
        1.  `AWS_ACCOUNT_ID`
        1.  `AWS_ACCESS_KEY_ID`
        1.  `AWS_SECRET_ACCESS_KEY`
        1.  `AWS_REGION`
    1.  Navigate to GitHub Project Actions tab, select the workflow `Build and Deploy Prefect Flow to ECR`, and click the green "Run workflow" button to deploy the Prefect flow
    	  1. Confirm it was deployed sucessfully by visiting the "Deployments" section of the Prefect UI
1.  Confirm your email subscription to the pipeline SNS topic
    1.  Navigate to the inbox of the email address you configured in `stg.tfvars` and look for an email subject titled `AWS Notification - Subscription Confirmation`.
    1.  Open the email and click the `Confirm Subscription` link within.
    1.  Verify you see a green message relaying your subscription has been confirmed.

## Platform ECS Services

Once the Terraform `make apply` command completes successfully, you should see output similar to the following that provides you URLs to each of the created tools:
```
🎉 All systems go! 🎉

MLflow, Optuna, Prefect, Evidently, and Grafana UI URLs
-------------------------------------------------------

🧪 MLflow UI: http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:5000
🔍 Optuna UI: http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:8080
⚙️ Prefect UI: http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:4200
📈 Evidently UI: http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:8000
📈 Grafana UI: http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:3000
```

Clicking on each URL should render each tool's UI successfully in your browser (the Terraform command includes invoking a script that polls the services' URLs until they return successful responses).

If any of the URLs return an error (e.g. 503 Service Unavailable), investigate the root cause by logging into the AWS Elastic Container Service (ECS) console and inspect the logs of the ECS Task that is failing.

If all the services started auccessfully, your ECS Task list should look similar to this screenshot:

![Platform ECS Tasks Screenshot](readme-assets/pipeline_ecs_tasks.png)

These URLs were also written to the `{REPO_DIR}/.env` file for future retrieval and export to shell environment when needed.

```
OPTUNA_DB_CONN_URL=postgresql+psycopg2://USERNAME:PASSWORD@your-project-id-postgres.abcdefghijk.us-east-2.rds.amazonaws.com:5432/optuna_db
MLFLOW_TRACKING_URI=http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:5000
PREFECT_API_URL=http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:4200/api
EVIDENTLY_UI_URL=http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:8000
PREFECT_UI_URL=http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:4200
GRAFANA_UI_URL=http://your-project-id-alb-123456789.us-east-2.elb.amazonaws.com:3000
```

The following sections give a brief overview of the tool features made available in this project:

### MLflow Tracking Server & Model Registry
* List model experiment runs that track model metrics and parameters used
* Captures details of each experiment run, including model type and training dataset used
* Automatically creates images to aid evaluation (e.g. confusion matrix, SHAP summary plot)
* Store models in Model Registry for future use (e.g. loaded by Model Evaluation Pipeline on file drop)

![MLflow Experiments](readme-assets/mlflow-experiments.png) <br>
![MLflow Model Details](readme-assets/mlflow-model-details.png)
![MLflow Artifacts](readme-assets/mlflow-artifacts.png)
![MLflow Confusion Matrix](readme-assets/mlflow-confusion-matrix.png)
![MLflow Registry](readme-assets/mlflow-model-registry.png)

### Optuna Hyperparameter Tuning Dashboard
Gain insight on Optuna hyperparameter tuning trials to narrow parameter search spaces and more quickly find optimal parameters.

![Optuna Dashboard Top](readme-assets/optuna-dashboard-top.png)
![Optuna Dashboard Top](readme-assets/optuna-dashboard-middle.png)
![Optuna Dashboard Top](readme-assets/optuna-dashboard-bottom.png)
![Optuna Dashboard Top](readme-assets/optuna-analytics-top.png)
![Optuna Dashboard Top](readme-assets/optuna-analytics-middle.png)
![Optuna Dashboard Top](readme-assets/optuna-analytics-middle-middle.png)
![Optuna Dashboard Top](readme-assets/optuna-analytics-bottom.png)

### Prefect Orchestration Server and Worker Service

View completed, running, and failed model evaluation runs to monitor pipeline health and address any unexpected issues.

![Prefect Dashboard](readme-assets/prefect-dashboard.png)
![Prefect Runs](readme-assets/prefect-runs.png)
![Prefect Run Detail](readme-assets/prefect-run-detail.png)
![Prefect Flows](readme-assets/prefect-flows.png)
![Prefect Deployments](readme-assets/prefect-deployments.png)
![Prefect Work Pools](readme-assets/prefect-work-pools.png)

### Evidently Non-Time-Series Dashboard and Reports UI

Assess dataset drift and model performance for each new churn data drop to decide whether model retraining is needed.

![Evidently Data Drift Summary](readme-assets/evidently-data-drift-summary.png)
![Evidently Data Drift Detailed](readme-assets/evidently-data-drift-detailed.png)
![Evidently Model Performance](readme-assets/evidently-model-performance.png)
![Evidently Confusion Matrix](readme-assets/evidently-confusion-matrix.png)
![Evidently Confusion Matrix By Label](readme-assets/evidently-confusion-matrix-by-label.png)

### Grafana Time-Series Dashboard UI

Provides a pre-created dashboard plotting model data drift and performance metrics over time to distinguish anomalies from signals suggesting model development is needed.

![Grafana Latest Prediction Scores](readme-assets/grafana-latest-prediction-scores.png)
![Grafana Drift Summary Metrics](readme-assets/grafana-drift-summary-metrics.png)
![Grafana Metric Drift p-Values](readme-assets/grafana-metric-drift-p-values.png)

## How to Upload Data

1. Navigate to `{REPO_DIR}` (and run `cd code/orchestration && pipenv shell` if you haven't already)
2. You can process the labeled Customer Churn data in one of two ways:

   1. Use `upload_simulation_script.py` script to upload non-training data files 30-seconds apart to [S3 File Drop `input` Folder](#s3-file-drop-folder-structure)

      1. Edit `upload_simulation_script.py` to change the `BUCKET_NAME` value to match the `project_id` you configured in `stg.tfvars`
      1. Run `make simulate-file-drops` from `{REPO_DIR}` to run the script `upload_simulation_script.py` which uploads each file in the `data` folder (except `customer_churn_0.csv`) to the S3 bucket folder

   2. Manually upload files from the `{REPO_DIR}/data` folder into the S3 bucket `{PROJECT_ID}/data/input` folder


## How to Evaluate Data Drift & Model

Once your files have completed processing (as visible via Prefect UI or seeing them appear in S3 `data/processed/` folder), you can evaluate their data in two ways:

1.  Navigate to the Evidently UI to view detailed data drift metrics and prediction scores for each file
2.  Navigate to the Grafana UI and view the pre-built **"Customer Churn Model Evaluation"** dashboard to view how the drift metrics and prediction scores have behaved over time

## Data Drift & Prediction Score Email Alerts

The pipeline will send an email to the address configured within `stg.tfvars` in each of the following scenarios:

### Data Drift Alert
Sent if Evidently finds more than 50% of the new customer data set columns have drifted from the reference data set:
![Data Drift Email Alert Example](readme-assets/email-alert-data-drift.png)

### Prediction Score Alert
Sent if Evidently reports any of the observed prediction scores drop below 70%:
* F1 Score
* Precision
* Recall
* Accuracy

![Data Drift Email Alert Example](readme-assets/email-alert-scores-below-threshold.png)

## Unit Test Examples

Example unit tests can be found within the `code/orchestration/tests/unit/` folder for select Prefect @task functions of `churn_prediction_pipeline.py`.

The `unittest.TestCase`, `unittest.mock.Patch`, and `unittest.mock.MagicMock` classes were used to create reused test fixture code that overrode ("patch"-ed) class object references with mock objects.

<pre>
├── code
│   ├── orchestration
│   │   ├── tests
│   │   │   ├── unit
│   │   │   │   ├── test_fetch_model.py
│   │   │   │   ├── test_generate_predictions.py
│   │   │   │   ├── test_move_to_folder.py
│   │   │   │   ├── test_prepare_dataset.py
│   │   │   │   └── test_validate_file_input.py
|   |   └── churn_prediction_pipeline.py
</pre>


## Integration Test Examples

Example integration tests can be found within the `code/orchestration/tests/integration/` folder for the `validate_file_input` @task function of `churn_prediction_pipeline.py`.

In order to integration test the function is correctly reading files from S3, the [`testcontainers.localstack` module ↗](https://testcontainers-python.readthedocs.io/en/latest/modules/localstack/README.html) was used to dynamically create a [LocalStack ↗](https://www.localstack.cloud) container that served as a mock S3 endpoint for the `s3_client` calls made by the `validate_file_input` function.

<pre>
├── code
│   ├── orchestration
│   │   ├── tests
│   │   │   ├── integration
│   │   │   │   └── test_validate_file_input.py
|   |   └── churn_prediction_pipeline.py
</pre>

## Pre-Commit Hooks

### How to Activate Pre-Commit Hooks

The following steps are required to activate pre-commit hooks for this repository:

1.  Navigate to `{REPO_DIR}/code/orchestration/` and run `pipenv shell` if you haven't already
2.  Navigate to `{REPO_DIR}` and run `pre-commit install`
3.  Ensure your Docker Engine is running (needed for LocalStack-based integration tests)
4.  Run `make quality` to generate the required `.pre-commit-config.yaml` file and execute the hooks

Generating `.pre-commit-config.yaml` was needed to inject the absolute path to the `code/orchestration/modeling` module folder for `pylint` (future improvement: use relative path instead).  For this reason, `.pre-commit-config.yaml` is included in `.gitignore` to not commit cleartext absolute path in case you commit your repo publicly.

### Hooks List

The following hooks are used to maintain notebook and module code quality and execute tests prior to commiting files to Git:

* `nbqa-pylint`
* `nbqa-flake8`
* `nbqa-black`
* `nbqa-isort`
* `trailing-whitespace`
* `end-of-file-fixer`
* `check-yaml`
* `check-added-large-files`
* `isort`
* `black`
* `pylint`
* `pytest-check`

## Makefile Targets

The following table lists the `make` targets available to accelerate platform deployment, development, and testing:
| Target Name | Purpose |
| ------------| ------- |
| `test` | Runs all unit and integration tests defined within `code/orchestration` and `code/s3_to_prefect_lambda` folders |
| `quality` | Runs `pre-commit run --all-files`.  See [Pre-Commit Hooks](#pre-commit-hooks) |
| `commit` | Stages all changed files, prompts user for commit message, and attempts to commit the files (barring pre-commit errors) |
| `plan` | Runs `terraform plan --var-file=vars/stg.tfvars` from `infrastructure` directory |
| `apply` | Runs `terraform apply --var-file=vars/stg.tfvars --auto-approve` and outputs emoji-filled message with UI URLs upon successful deploy and ECS Task activation |
| `destroy` | Runs `terraform destroy -var-file=vars/stg.tfvars --auto-approve` |
| `disable-lambda` | Used to facilitate local dev/testing: Disables notification of the `s3_to_prefect` Lambda function so files aren't automatically picked up by the deployed service.  Lets you drop file(s) manually in S3 and run the pipeline locally when you're ready (see `process-test-data` target below). |
| `enable-lambda` | Re-enables the `s3_to_prefect` Lambda notification to resume creating new Prefect flow runs on S3 file drop |
| `deploy-model` | <ul><li>Executes the `churn_model_training.py` file to train and deploy two models to the MLflow Registry (evaluated on training and holdout data, respectively).</li><li>The second model is assigned the `staging` alias to allow the Prefect pipeline to fetch the latest `staging` model without code changes.</li><li>Note: Hyperparameter tuning is NOT performed with this target to accelerate model deployment.  See `log-model-nopromote` target if hyperparameter tuning is desired.</li></ul> |
| `log-model-nopromote` | <ul><li>Executes the `churn_model_training.py` file to train and deploy two models to MLflow without executing promotion steps (e.g. does not apply `staging` alias).</li><li>Used to develop and optimize model performance prior to making it available for stakeholder use.</li><li>**Hyperparameter Tuning Notes:**<ul><li>Optuna Bayesian hyperparameter tuning is performed with this target, with the number of trials currently set to 50.</li><li>Modify churn_model_training.py to adjust the number of trials if desired.  Optuna recommends executing at least 20-30 trials to accumulate enough prior runs to optimize parameters.</li><li>Allot approximately 10 minutes for the trials to complete (actual time varies based on local machine performance and network connectivity).</li><li>Suggested optimization approach:<ul><li>Use the Optuna UI to correlate parameter ranges with higher F1 scores</li><li>Use insights to narrow the parameter search space used in `churn_model_training.py`</li><li>Once you've chosen the optimal parameters, modify the `best_params_to_date` variable in `churn_model_training.py` so that they are used in subsequent executions of the `deploy-model` target</li></ul></li></li></ul></li></ul>  |
| `process-test-data` | Use to manually invoke flow after running `disable-lambda` target.  **Upload `customer_churn_1.csv` into the S3 `data/input/` folder before use.**  Runs command `python churn_prediction_pipeline.py your-project-id data/input/customer_churn_1.csv` and instantiates ephemeral local Prefect Server to execute flow. |
| `simulate-file-drops` | Runs `upload_simulation_script.py` to automatically upload each non-training data file in the `data/` folder to the S3 File Drop input folder. |

## CI-CD Implementation

[GitHub Actions ↗](https://github.com/features/actions) was used to execute the following Continuous integration and Continuous Delivery (CI/CD) process.  See `.github/workflows/deploy-prefect.yml` for details.

```mermaid
flowchart TD
    A[Commit changes to code/orchestration/ tree]
    B[Manually run workflow from GitHub UI]
    C[Initialize ubuntu-latest Runner VM]
    D[Checkout code]
    E[Set up Python]
    F[Install Pipenv]
    G[Install code/orchestration/ Pipfile dependencies]
    H[Configure AWS credentials]
    I[Run unit and integration tests]
    J[Log in to Amazon ECR]
    K[Construct Prefect Flow Docker image name & tag]
    L[Inject Docker image name & tag into Prefect Flow YAML]
    M[Display YAML in GitHub Actions log for verification]
    N[Install Prefect]
    O[Build Docker container & deploy to Prefect Server]
    A-->C;
    B-->C;
    C-->D-->E-->F-->G-->H-->I-->J-->K-->L-->M-->N-->O;
```

## DataTalks.club MLOps Zoomcamp Evaluation Criteria
Source: https://github.com/DataTalksClub/mlops-zoomcamp/tree/main/07-project

### Problem description
#### Target: The problem is well described and it's clear what the problem the project solves
See [Problem Statement](#problem-statement) section.

### Cloud
#### Target: The project is developed on the cloud and IaC tools are used for provisioning the infrastructure
* See [Project Folders & Files](#project-folders--files) section for summary of Terraform files used to create AWS infrastructure.
* See [Platform Infrastructure Diagram](#platform-infrastructure-diagram) for diagram of cloud resources created and collaborations for each.

### Experiment tracking and model registry
#### Target: Both experiment tracking and model registry are used
See [MLflow Tracking Server & Model Registry](#mlflow-tracking-server--model-registry) section for screenshots of experiments tracked and model stored in registry.

### Workflow orchestration
#### Target: Fully deployed workflow
See [Prefect Orchestration Server and Worker Service](#prefect-orchestration-server-and-worker-service) section for screenshots of fully deployed workflow within Prefect UI and examples of worflow executions ("runs").

### Model deployment
#### Target: The model deployment code is containerized and could be deployed to cloud or special tools for model deployment are used
See the `orchestration` and `s3_to_prefect_lambda` folders of [Project Folders & Files](#project-folders--files) to see how the model deployment code was containerized and deployed to the cloud.

### Model monitoring
#### Target: Comprehensive model monitoring that sends alerts or runs a conditional workflow (e.g. retraining, generating debugging dashboard, switching to a different model) if the defined metrics threshold is violated
See [Data Drift & Prediction Score Email Alerts](#data-drift--prediction-score-email-alerts) section for examples of email alerts that are sent when new customer data files exhibit the majority of their columns drifting from reference data or when the model prediction scores drop below pre-defined threshold.

### Reproducibility
#### Target: Instructions are clear, it's easy to run the code, and it works. The versions for all the dependencies are specified.
* See [How to Install Platform](#how-to-install-platform) section for instructions on how to set up the platform.
* See [Library Dependencies & Version Numbers](#library-dependencies--version-numbers) section for instructions on how to determine libraries used and their verision numbers.

### Best practices
#### Target: There are unit tests (1 point)
See [Unit Test Examples](#unit-test-examples) section for summary of unit tests that were implemented.

#### Target: There is an integration test (1 point)
See [Integration Test Examples](#integration-test-examples) section for summary of integration tests that were implemented.

#### Target: Linter and/or code formatter are used (1 point)
See [Pre-Commit Hooks](#pre-commit-hooks) section to see which linter and code formatters were used.

#### Target: There's a Makefile (1 point)
See [Makefile Targets](#makefile-targets) section for list of `Makefile` targets that were implemented.

#### Target: There are pre-commit hooks (1 point)
See [Pre-Commit Hooks](#pre-commit-hooks) section to see which hooks were used.

#### Target: There's a CI/CD pipeline (2 points)
See [CI-CD Implementation](#ci-cd-implementation) section for summary of how CI/CD was implemented.
