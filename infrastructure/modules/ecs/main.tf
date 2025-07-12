resource "aws_security_group" "mlflow_ecs" {
  name   = "${var.project_id}_mlflow_ecs_sg"
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

resource "aws_iam_role_policy_attachment" "mlflow_s3_access" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "mlflow_logs_access" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_role_policy_attachment" "mlflow_ecr_access" {
  role       = aws_iam_role.mlflow_task_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_cloudwatch_log_group" "mlflow_logs" {
  name              = "/ecs/${var.project_id}-mlflow"
  retention_in_days = 7 
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
        "--backend-store-uri", "postgresql://${var.db_username}:${var.db_password}@${var.mlflow_db_endpoint}/${var.db_name}",
        "--default-artifact-root", "s3://${var.project_id}/mlflow/",
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
  name            = "${var.project_id}-mlflow-service"
  cluster         = aws_ecs_cluster.mlflow_cluster.id
  task_definition = aws_ecs_task_definition.mlflow.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  force_new_deployment = true

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = true
    security_groups  = [aws_security_group.mlflow_ecs.id]
  }
}

resource "null_resource" "get_mlflow_tracking_uri" {
  provisioner "local-exec" {
    command = <<EOT
      set -e

      echo "Fetching ECS task ID..."
      CLUSTER_NAME="${var.project_id}-mlflow-cluster"
      SERVICE_NAME="${var.project_id}-mlflow-service"
      TASK_ID=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name $SERVICE_NAME --query 'taskArns[0]' --output text)

      echo "Getting ENI ID from task..."
      ENI_ID=$(aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ID \
        --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

      echo "Getting Public IP from ENI..."
      PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID \
        --query 'NetworkInterfaces[0].Association.PublicIp' --output text)

      echo "Writing MLFLOW_TRACKING_URI to .env..."
      MLFLOW_TRACKING_URI="http://$PUBLIC_IP:5000"
      ENV_FILE="../.env"
      MAX_RETRIES=20
      SLEEP_SECONDS=15

      # Wait for task
      echo "Waiting for ECS task..."
      i=1
      while [ "$i" -le "$MAX_RETRIES" ]; do
        TASK_ARN=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --desired-status RUNNING --query 'taskArns[0]' --output text)
        if [ "$TASK_ARN" != "None" ] && [ -n "$TASK_ARN" ]; then
          echo "Task found: $TASK_ARN"
          break
        fi
        echo "Retry $i/$MAX_RETRIES: No running task yet..."
        sleep "$SLEEP_SECONDS"
        i=$((i + 1))
      done

      if [ -z "$TASK_ARN" ] || [ "$TASK_ARN" = "None" ]; then
        echo "Timed out waiting for ECS task."
        exit 1
      fi

      # Wait for ENI and public IP
      echo "Waiting for ENI and Public IP..."
      i=1
      while [ "$i" -le "$MAX_RETRIES" ]; do
        ENI_ID=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" \
          --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

        if [ -n "$ENI_ID" ] && [ "$ENI_ID" != "None" ]; then
          PUBLIC_IP=$(aws ec2 describe-network-interfaces \
            --network-interface-ids "$ENI_ID" \
            --query 'NetworkInterfaces[0].Association.PublicIp' --output text)

          if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "None" ]; then
            echo "Public IP: $PUBLIC_IP"
            break
          fi
        fi

        echo "Retry $i/$MAX_RETRIES: Waiting for ENI/Public IP..."
        sleep "$SLEEP_SECONDS"
        i=$((i + 1))
      done

      if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" = "None" ]; then
        echo "Timed out waiting for public IP."
        exit 1
      fi

      # Write to .env safely

      # Replace the line if it exists, otherwise append it
      if grep -q "^MLFLOW_TRACKING_URI=" "$ENV_FILE"; then
          sed -i.bak "s|^MLFLOW_TRACKING_URI=.*|MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI|" "$ENV_FILE"
      else
          echo "MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI" >> "$ENV_FILE"
      fi

      echo "MLFLOW_TRACKING_URI set to $MLFLOW_TRACKING_URI in $ENV_FILE"
    EOT
  }

  depends_on = [aws_ecs_service.mlflow] 
}
