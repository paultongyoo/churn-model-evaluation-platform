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

variable "my_ip" {
  description = "Your public IP in CIDR notation (e.g. '203.0.113.5/32')"
}

variable "ecs_sg_id" {
  description = "Security group ID for the ECS tasks"
  type        = string
}

variable "db_username" {
  description = "RDS database username"
  type        = string
}

variable "db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "db_endpoint" {
  description = "RDS database endpoint"
  type        = string
}
