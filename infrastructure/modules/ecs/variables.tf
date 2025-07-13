variable "project_id" {
    description = "The project ID for the infrastructure"
    type        = string
}

variable "aws_region" {
    description = "The AWS region to deploy resources in"
    type        = string
}

variable "vpc_id" {
    description = "The VPC ID for the infrastructure"
    type        = string
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of subnet IDs in different AZs"
}

variable "mlflow_image_uri" {
    description = "The Docker image for the MLflow container"
    type        = string
}

variable "db_username" {
  description = "RDS database username"
  type        = string
}

variable "db_endpoint" {
  description = "RDS database endpoint"
  type        = string
}

variable "db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "rds_sg_id" {
  description = "Security group ID for the RDS instance"
  type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  type        = string
}

variable "prefect_target_group_arn" {
  description = "ARN of the Prefect target group"
  type        = string
}

variable "mlflow_target_group_arn" {
  description = "ARN of the MLflow target group"
  type        = string
}

variable "alb_sg_id" {
  description = "Security group ID for the Application Load Balancer"
  type        = string
}
