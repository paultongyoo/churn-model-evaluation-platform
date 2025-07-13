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
    mlflow_image_uri = module.ecr.image_uri
    db_username = var.db_username
    db_password = var.db_password
    db_endpoint = module.rds_postgres.endpoint
    #my_ip = var.my_ip
    rds_sg_id = module.rds_postgres.sg_id
    alb_dns_name = module.alb.alb_dns_name
    alb_sg_id = module.alb.alb_sg_id
    prefect_target_group_arn = module.alb.prefect_target_group_arn
    mlflow_target_group_arn = module.alb.mlflow_target_group_arn
}

module "alb" {
  source     = "./modules/alb"
  project_id = var.project_id
  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids
  my_ip = var.my_ip
}
