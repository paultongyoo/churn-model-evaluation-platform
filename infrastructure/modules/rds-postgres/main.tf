resource "aws_db_subnet_group" "default" {
  name       = "${var.project_id}_rds-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.project_id} RDS subnet group"
  }
}

resource "aws_security_group" "rds_sg" {
  name        = "${var.project_id}_rds_sg"
  description = "RDS SG"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier         = var.db_identifier
  engine             = "postgres"
  engine_version     = "15.10"
  instance_class     = "db.t3.micro"
  allocated_storage  = 20
  db_name            = var.db_name
  username           = var.db_username
  password           = var.db_password
  db_subnet_group_name = aws_db_subnet_group.default.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  skip_final_snapshot = true
  publicly_accessible = false
  multi_az           = false
  storage_encrypted  = true
}