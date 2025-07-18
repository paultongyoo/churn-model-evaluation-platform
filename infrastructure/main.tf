terraform {
    required_version = ">= 1.8"
    backend "s3" {
        bucket = "mlops-churn-pipeline-tf-state"
        key     = "mlops-churn-pipeline.tfstate"
        region  = "us-east-2"
        encrypt = true
    }
    required_providers {
        local = {
            source  = "hashicorp/local"
            version = "~> 2.0"
        }
    }
}

provider "aws" {
    region = var.aws_region
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
    db_identifier = "${var.project_id}-postgres"
    db_username = var.db_username
    db_password = var.db_password
    my_ip = var.my_ip
    ecs_sg_id = module.ecs_stack.ecs_sg_id
}

module "ecr" {
    source = "./modules/ecr"
    project_id = var.project_id
    aws_region = var.aws_region
}

module "ecs_stack" {
    source = "./modules/ecs"
    project_id = var.project_id
    aws_region = var.aws_region
    vpc_id = var.vpc_id
    subnet_ids = var.subnet_ids
    db_username = var.db_username
    db_password = var.db_password
    db_endpoint = module.rds_postgres.endpoint
    rds_sg_id = module.rds_postgres.sg_id
    alb_dns_name = module.alb.alb_dns_name
    alb_sg_id = module.alb.alb_sg_id
    prefect_target_group_arn = module.alb.prefect_target_group_arn
    mlflow_target_group_arn = module.alb.mlflow_target_group_arn
    evidently_ui_target_group_arn = module.alb.evidently_ui_target_group_arn
    bucket_arn = module.s3_bucket.bucket_arn
    mlflow_tracking_uri = module.alb.mlflow_tracking_uri
}

module "alb" {
    source     = "./modules/alb"
    project_id = var.project_id
    vpc_id     = var.vpc_id
    subnet_ids = var.subnet_ids
    my_ip = var.my_ip
    ecs_sg_id = module.ecs_stack.ecs_sg_id
    db_username = var.db_username
    db_password = var.db_password
    db_endpoint = module.rds_postgres.endpoint
}

module "s3_to_prefect_lambda" {
    source = "./modules/s3-to-prefect-lambda"
    project_id = var.project_id
    bucket_arn = module.s3_bucket.bucket_arn
    bucket_id = module.s3_bucket.bucket_id
    s3_to_prefect_lambda_image_uri = module.ecr.s3_to_prefect_lambda_image_uri
    alb_dns_name = module.alb.alb_dns_name
    lambda_filter_prefix = var.lambda_filter_prefix
}
