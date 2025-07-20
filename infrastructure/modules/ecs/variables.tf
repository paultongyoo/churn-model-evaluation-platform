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

variable "evidently_ui_target_group_arn" {
  description = "ARN of the Evidently UI target group"
  type        = string
}

variable "grafana_target_group_arn" {
  description = "ARN of the Grafana target group"
  type        = string
}

variable "alb_sg_id" {
  description = "Security group ID for the Application Load Balancer"
  type        = string
}

variable "bucket_arn" {
  description = "ARN of the S3 bucket"
  type        = string
}

variable "mlflow_tracking_uri" {
  description = "MLflow tracking URI"
  type        = string
}

variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
}

variable "grafana_anon_org_name" {
  description = "Name of the anonymous organization in Grafana"
  type        = string
  default     = "Main Org."
}

variable "grafana_image_uri" {
  description = "URI of the Grafana Docker image in ECR"
  type        = string
}
