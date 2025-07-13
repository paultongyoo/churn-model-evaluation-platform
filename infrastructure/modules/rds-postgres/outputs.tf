output "endpoint" {
  value = aws_db_instance.postgres.endpoint
}

output "db_name" {
  value = aws_db_instance.postgres.db_name
}

output "sg_id" {
  value = aws_security_group.rds_sg.id
}
