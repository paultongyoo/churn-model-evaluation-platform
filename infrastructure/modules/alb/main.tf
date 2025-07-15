# Security group for the ALB
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_id}-alb-sg"
  description = "Allow HTTP access from my IP"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 4200
    to_port     = 4200
    protocol    = "tcp"
    #cidr_blocks = ["${var.my_ip}/32"]

    # Gives GitHub Actions access to deploy Prefect flows
    # Not recommended for production environments!
    # Production approach would be to inject GitHub Actions IPs from the official list
    cidr_blocks = ["0.0.0.0/0"]

    description = "Allows public access (incl GitHub Actions) to Prefect UI/API"
  }

  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["${var.my_ip}/32"]
    description = "Allow MLFlow from my IP"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "main" {
  name               = "${var.project_id}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = var.subnet_ids
}

# Target groups for MLflow and Prefect
resource "aws_lb_target_group" "mlflow" {
  name        = "${var.project_id}-mlflow-tg"
  port        = 5000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
}

resource "aws_lb_target_group" "prefect" {
  name        = "${var.project_id}-prefect"
  port        = 4200
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
}

# Listeners
resource "aws_lb_listener" "mlflow" {
  load_balancer_arn = aws_lb.main.arn
  port              = 5000
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mlflow.arn
  }
}

resource "aws_lb_listener" "prefect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 4200
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prefect.arn
  }
}

resource "null_resource" "write_service_urls_to_env" {
  provisioner "local-exec" {
    command = <<EOT
      set -e

      ENV_FILE="../.env"
      WORKFLOW_FILE="../.github/workflows/deploy-prefect.yml"
      MAX_RETRIES=20
      SLEEP_SECONDS=5
      PROJECT_ID="${var.project_id}"

      echo "Waiting for ALB DNS name..."

      i=1
      while [ "$i" -le "$MAX_RETRIES" ]; do
        DNS_NAME="${aws_lb.main.dns_name}"
        if [[ -n "$DNS_NAME" && "$DNS_NAME" != "None" ]]; then
          echo "ALB DNS Name found: $DNS_NAME"
          break
        fi
        echo "Retry $i/$MAX_RETRIES: Waiting for ALB DNS name..."
        sleep "$SLEEP_SECONDS"
        i=$((i + 1))
      done

      if [ -z "$DNS_NAME" ] || [ "$DNS_NAME" = "None" ]; then
        echo "Timed out waiting for ALB DNS name."
        exit 1
      fi

      echo "Updating .env file with MLFLOW_TRACKING_URI and PREFECT_API_URL..."

      MLFLOW_TRACKING_URI="http://$DNS_NAME:5000"
      PREFECT_API_URL="http://$DNS_NAME:4200/api"

      # --- Update .env file ---
      if grep -q "^MLFLOW_TRACKING_URI=" "$ENV_FILE"; then
        sed -i.bak "s|^MLFLOW_TRACKING_URI=.*|MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI|" "$ENV_FILE"
      else
        echo "MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI" >> "$ENV_FILE"
      fi

      if grep -q "^PREFECT_API_URL=" "$ENV_FILE"; then
        sed -i.bak "s|^PREFECT_API_URL=.*|PREFECT_API_URL=$PREFECT_API_URL|" "$ENV_FILE"
      else
        echo "PREFECT_API_URL=$PREFECT_API_URL" >> "$ENV_FILE"
      fi

      ## --- Update deploy-prefect.yml env block ---
      if grep -q "MLFLOW_TRACKING_URI:" "$WORKFLOW_FILE"; then
        sed -i.bak "s|MLFLOW_TRACKING_URI:.*|MLFLOW_TRACKING_URI: $MLFLOW_TRACKING_URI|" "$WORKFLOW_FILE"
      else
        echo "WARNING: MLFLOW_TRACKING_URI not found in $WORKFLOW_FILE"
      fi

      if grep -q "PREFECT_API_URL:" "$WORKFLOW_FILE"; then
        sed -i.bak "s|PREFECT_API_URL:.*|PREFECT_API_URL: $PREFECT_API_URL|" "$WORKFLOW_FILE"
      else
        echo "WARNING: PREFECT_API_URL not found in $WORKFLOW_FILE"
      fi

      echo "✅ Files updated:"
      echo "  .env -> MLFLOW_TRACKING_URI=$MLFLOW_TRACKING_URI"
      echo "  .env -> PREFECT_API_URL=$PREFECT_API_URL"
      echo "  deploy-prefect.yml updated if env keys were found"
    EOT
    interpreter = ["/bin/bash", "-c"]
  }

  depends_on = [aws_lb.main]
}
