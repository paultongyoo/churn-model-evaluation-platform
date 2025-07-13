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
