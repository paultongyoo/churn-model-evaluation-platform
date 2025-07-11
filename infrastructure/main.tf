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
    bucket_name = "${var.model_bucket}"
}