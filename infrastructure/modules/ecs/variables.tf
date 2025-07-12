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

variable "mlflow_db_endpoint" {
  description = "RDS database endpoint"
  type        = string
}

variable "db_name" {
  description = "Name of the RDS database"
  type        = string
}

variable "db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "my_ip" {
  description = "Your public IP in CIDR notation (e.g. '203.0.113.5/32')"
}

variable "rds_sg_id" {
  description = "Security group ID for the RDS instance"
  type        = string
}
