variable "project_id" {
    description = "The project ID for the infrastructure"
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

variable "mlflow_db_identifier" {
  description = "Identifier for the RDS instance"
  type        = string
}

variable "mlflow_db_name" {
  description = "Name of the RDS database"
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

