resource "aws_security_group" "mlflow_ecs" {
  name   = "${var.project_id}_mlflow_ecs_sg"
  vpc_id = var.vpc_id
}

resource "aws_security_group_rule" "ecs_to_rds" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = var.rds_sg_id
  source_security_group_id = aws_security_group.mlflow_ecs.id
}

resource "aws_security_group_rule" "allow_my_ip_to_mlflow" {
  type              = "ingress"
  from_port         = 5000
  to_port           = 5000
  protocol          = "tcp"
  security_group_id = aws_security_group.mlflow_ecs.id
  cidr_blocks       = [var.my_ip]
  description       = "Allow MLflow access from my IP only"
}

resource "aws_iam_role" "mlflow_task_exec_role" {
  name = "mlflow-task-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "mlflow_s3_access" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_ecs_task_definition" "mlflow" {
  family                   = "mlflow"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.mlflow_task_exec_role.arn
  task_role_arn            = aws_iam_role.mlflow_task_exec_role.arn

  container_definitions = jsonencode([
    {
      name      = "mlflow"
      image     = var.mlflow_container_image
      essential = true
      portMappings = [
        {
          containerPort = 5000
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "BACKEND_STORE_URI"
          value = "postgresql://${var.mlflow_db_username}:${var.mlflow_db_password}@${var.mlflow_db_endpoint}:5432/${var.mlflow_db_name}"
        },
        {
          name  = "ARTIFACT_ROOT"
          value = "s3://${var.project_id}/mlflow/"
        }
      ]
      command = [
        "mlflow", "server",
        "--backend-store-uri", "$BACKEND_STORE_URI",
        "--default-artifact-root", "$ARTIFACT_ROOT",
        "--host", "0.0.0.0",
        "--port", "5000"
      ]
    }
  ])
}

resource "aws_ecs_cluster" "mlflow_cluster" {
  name = "${var.project_id}-mlflow-cluster"
}

resource "aws_ecs_service" "mlflow" {
  name            = "mlflow-service"
  cluster         = aws_ecs_cluster.mlflow_cluster.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = false
    security_groups  = [aws_security_group.mlflow_ecs.id]
  }
}
