terraform {
    required_version = ">= 1.8"
    backend "s3" {
        bucket = "mlops-churn-pipeline-tf-state"
        key     = "mlops-churn-pipeline.tfstate"
        region  = "us-east-2"
        encrypt = true
    }
}

provider "aws" {
    region = var.aws_region
}

data "aws_caller_identity" "current_identity" {}

locals {
    account_id = data.aws_caller_identity.current_identity.account_id
}

module "s3_bucket" {
    source = "./modules/s3"
    bucket_name = "${var.project_id}"
}

module "rds_postgres" {
    source = "./modules/rds-postgres"
    project_id = var.project_id
    vpc_id = var.vpc_id
    subnet_ids = var.subnet_ids
    mlflow_db_identifier = "${var.project_id}-postgres"
    mlflow_db_name = var.mlflow_db_username
    mlflow_db_username = var.mlflow_db_username
    mlflow_db_password = var.mlflow_db_password
}

module "ecs_stack" {
    source = "./modules/ecs"
    project_id = var.project_id
    vpc_id = var.vpc_id
    subnet_ids = var.subnet_ids
    mlflow_db_username = var.mlflow_db_username
    mlflow_db_password = var.mlflow_db_password
    mlflow_db_endpoint = module.rds_postgres.endpoint
    mlflow_db_name = module.rds_postgres.db_name
    my_ip = var.my_ip
    rds_sg_id = module.rds_postgres.sg_id
}