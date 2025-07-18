output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "alb_sg_id" {
  value = aws_security_group.alb_sg.id
}

output "mlflow_target_group_arn" {
  value = aws_lb_target_group.mlflow.arn
}

output "prefect_target_group_arn" {
  value = aws_lb_target_group.prefect.arn
}

output "evidently_ui_target_group_arn" {
  value = aws_lb_target_group.evidently_ui.arn
}

output "mlflow_tracking_uri" {
  value = "http://${aws_lb.main.dns_name}:5000"
}
