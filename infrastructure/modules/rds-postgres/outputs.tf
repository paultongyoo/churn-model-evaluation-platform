output "endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "sg_id" {
  value = aws_security_group.rds_sg.id
}
