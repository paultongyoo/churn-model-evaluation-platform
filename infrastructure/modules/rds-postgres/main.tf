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

  ingress {
    description = "Allow PostgreSQL from my IP"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["${var.my_ip}/32"]
  }

  ingress {
    from_port                = 5432
    to_port                  = 5432
    protocol                 = "tcp"
    security_groups          = [var.ecs_sg_id]
  }

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
  db_name            = "postgres"       # Initial database only
  username           = var.db_username
  password           = var.db_password
  db_subnet_group_name = aws_db_subnet_group.default.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  skip_final_snapshot = true

  # Required for local-exec DB creation and public access
  # Can be set to false after DBs are created and no public access is needed
  publicly_accessible = true

  multi_az           = false
  storage_encrypted  = true
}

resource "null_resource" "create_additional_dbs" {
  depends_on = [aws_db_instance.postgres]

  provisioner "local-exec" {
    command = <<EOT
      echo "Checking for psql..."
      if ! command -v psql > /dev/null; then
        echo "ERROR: psql is not installed. Please install the PostgreSQL client CLI." >&2
        exit 1
      fi

      echo "Waiting for RDS to become available..."
      for i in {1..30}; do
        pg_isready -h ${aws_db_instance.postgres.address} -U ${var.db_username} && break
        sleep 10
      done

      echo "Creating mlflow_db..."
      PGPASSWORD='${var.db_password}' psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d postgres -c "CREATE DATABASE mlflow_db;"

      echo "Creating optuna_db..."
      PGPASSWORD='${var.db_password}' psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d postgres -c "CREATE DATABASE optuna_db;"

      echo "Creating prefect_db..."
      PGPASSWORD='${var.db_password}' psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d postgres -c "CREATE DATABASE prefect_db;"

      echo "Creating metrics_db..."
      PGPASSWORD='${var.db_password}' psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d postgres -c "CREATE DATABASE metrics_db;"
    EOT

    interpreter = ["/bin/bash", "-c"]
  }
}

resource "null_resource" "write_optuna_db_conn_url_to_env_file" {
  provisioner "local-exec" {
    command = <<EOT
      set -e

      ENV_FILE="../.env"
      OPTUNA_DB_CONN_URL="postgresql+psycopg2://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/optuna_db"

      if /usr/bin/grep -q "OPTUNA_DB_CONN_URL=" "$ENV_FILE"; then
        /usr/bin/sed -i "s|OPTUNA_DB_CONN_URL=.*|OPTUNA_DB_CONN_URL=$OPTUNA_DB_CONN_URL|" "$ENV_FILE"
      else
        echo "OPTUNA_DB_CONN_URL=$OPTUNA_DB_CONN_URL" >> "$ENV_FILE"
      fi

      echo "📝 Updated $ENV_FILE -> OPTUNA_DB_CONN_URL=$OPTUNA_DB_CONN_URL"

    EOT
    interpreter = ["/bin/bash", "-c"]
  }

  depends_on = [null_resource.create_additional_dbs]
}
