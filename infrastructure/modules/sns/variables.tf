variable "project_id" {
    description = "The project ID for the infrastructure"
    type        = string
}

variable "my_email_address" {
  description = "Email address to receive SNS alerts"
  type        = string
}

variable "prefect_worker_task_exec_role_arn" {
  description = "ARN of the IAM role for Prefect worker tasks"
  type        = string
}
