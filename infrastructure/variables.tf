variable "aws_region" {
    description = "The AWS region to deploy resources in"
    type        = string
    default     = "us-east-2"
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

variable "mlflow_db_name" {
  description = "RDS database name.  Must be alphanumeric characters only."
  type        = string
}

variable "mlflow_db_username" {
  description = "RDS database username"
  type        = string
}

variable "mlflow_db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "my_ip" {
  description = "Your public IP in CIDR notation (e.g. '203.0.113.5/32')"
}


