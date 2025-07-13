data "aws_caller_identity" "current_identity" {}

locals {
    account_id = data.aws_caller_identity.current_identity.account_id
}

resource "aws_security_group" "ecs_sg" {
  name   = "${var.project_id}_ecs_sg"
  vpc_id = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "ecs_to_rds" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = var.rds_sg_id
  source_security_group_id = aws_security_group.ecs_sg.id
}

resource "aws_security_group_rule" "allow_alb_to_mlflow" {
  type                     = "ingress"
  from_port                = 5000
  to_port                  = 5000
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_sg.id
  source_security_group_id = var.alb_sg_id
}

resource "aws_iam_role" "mlflow_task_exec_role" {
  name = "${var.project_id}-mlflow-task-exec-role"

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

resource "aws_iam_policy" "mlflow_s3_limited_access" {
  name = "${var.project_id}-mlflow-s3-access"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid: "AllowReadWriteToMlflowPrefix",
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::${var.project_id}/mlflow/*",
          "arn:aws:s3:::${var.project_id}"  # Required for ListBucket
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mlflow_s3_policy_attachment" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = aws_iam_policy.mlflow_s3_limited_access.arn
}

resource "aws_iam_policy" "mlflow_logs_write" {
  name = "${var.project_id}-mlflow-logs-write"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/ecs/${var.project_id}-mlflow:log-stream:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "mlflow_logs_write_attachment" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = aws_iam_policy.mlflow_logs_write.arn
}

resource "aws_iam_role_policy_attachment" "mlflow_ecr_access" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_cloudwatch_log_group" "mlflow_logs" {
  name              = "/ecs/${var.project_id}-mlflow"
  retention_in_days = 7
}

resource "aws_ecs_cluster" "mlops_cluster" {
  name = "${var.project_id}-mlops-cluster"
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
      image     = var.mlflow_image_uri
      essential = true
      portMappings = [
        {
          containerPort = 5000
          protocol      = "tcp"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_id}-mlflow",
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "ecs"
        }
      }
      command = [
        "mlflow", "server",
        "--backend-store-uri", "postgresql://${var.db_username}:${var.db_password}@${var.db_endpoint}/mlflow_db",
        "--default-artifact-root", "s3://${var.project_id}/mlflow/",
        "--host", "0.0.0.0",
        "--port", "5000"
      ]
    }
  ])
}

resource "aws_ecs_service" "mlflow" {
  name            = "${var.project_id}-mlflow-service"
  cluster         = aws_ecs_cluster.mlops_cluster.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  force_new_deployment = true

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = true
    security_groups  = [aws_security_group.ecs_sg.id]
  }

  load_balancer {
    target_group_arn = var.mlflow_target_group_arn
    container_name   = "mlflow"
    container_port   = 5000
  }
}

resource "aws_iam_role" "prefect_task_exec_role" {
  name = "${var.project_id}-prefect-task-exec-role"

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

resource "aws_ecs_task_definition" "prefect_server" {
  family                   = "prefect-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.prefect_task_exec_role.arn
  task_role_arn            = aws_iam_role.prefect_task_exec_role.arn

  container_definitions = jsonencode([
    {
      name      = "prefect-server"
      image     = "prefecthq/prefect:3.4.8-python3.9"
      essential = true
      environment = [
        {
          name  = "PREFECT_API_DATABASE_CONNECTION_URL"
          value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${var.db_endpoint}/prefect_db"
        },
        {
          name  = "PREFECT_UI_ENABLED"
          value = "true"
        },
        {
          name  = "PREFECT_API_URL"
          value = "http://${var.alb_dns_name}:4200/api"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_id}-prefect",
          "awslogs-region"        = var.aws_region,
          "awslogs-stream-prefix" = "ecs"
        }
      }
      portMappings = [{
        containerPort = 4200
      }]
      command   = ["prefect", "server", "start", "--host", "0.0.0.0"]
    }
  ])
}

resource "aws_iam_policy" "prefect_logs_write" {
  name = "${var.project_id}-prefect-logs-write"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/ecs/${var.project_id}-prefect:log-stream:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "prefect_logs_write_attachment" {
  role       = aws_iam_role.prefect_task_exec_role.name
  policy_arn = aws_iam_policy.prefect_logs_write.arn
}

resource "aws_cloudwatch_log_group" "prefect_logs" {
  name              = "/ecs/${var.project_id}-prefect"
  retention_in_days = 7
}

resource "aws_ecs_service" "prefect" {
  name            = "${var.project_id}-prefect-service"
  cluster         = aws_ecs_cluster.mlops_cluster.id
  task_definition = aws_ecs_task_definition.prefect_server.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  force_new_deployment = true

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = true
    security_groups  = [aws_security_group.ecs_sg.id]
  }

  load_balancer {
    target_group_arn = var.prefect_target_group_arn
    container_name   = "prefect-server"
    container_port   = 4200
  }
}

resource "aws_security_group_rule" "allow_alb_to_prefect" {
  type                     = "ingress"
  from_port                = 4200
  to_port                  = 4200
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_sg.id
  source_security_group_id = var.alb_sg_id
}
