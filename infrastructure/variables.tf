variable "aws_region" {
    description = "The AWS region to deploy resources in"
    type        = string
}

variable "project_id" {
    description = "The project ID for the infrastructure"
    type        = string
    default     = "mlops-churn-pipeline"
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

variable "db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "my_ip" {
  description = "Your public IP (e.g. '203.0.113.5')"
}

variable "lambda_filter_prefix" {
  description = "Prefix for S3 objects that trigger the Lambda function"
  type        = string
  default     = "data/input/"
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
  default     = "Anonymous"
}

variable "my_email_address" {
  description = "Email address to receive SNS alerts"
  type        = string
}
