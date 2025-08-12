output "ecs_sg_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_sg.id
}

output "prefect_worker_task_exec_role_arn" {
  description = "IAM role for Prefect worker tasks"
  value       = aws_iam_role.prefect_worker_task_exec_role.arn
}
