# Security group for the ALB
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_id}-alb-sg"
  description = "Allow HTTP access to Pipeline Services"
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

  # Allows Prefect Worker ECS Task to access MLflow via ALB
  # Configuring access by security group was not working for an unknown reason
  # This is a workaround to allow access from ECS tasks to MLflow via ALB
  # TODO: Investigate why security group access was not working
  ingress {
    from_port       = 5000
    to_port         = 5000
    protocol        = "tcp"
    #security_groups = [var.ecs_sg_id]
    cidr_blocks = ["0.0.0.0/0"]
    description     = "Allow ECS tasks to access MLflow via ALB on port 5000"
  }

  # Allows Prefect Worker ECS Task to access Evidently UI via ALB
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    #security_groups = [var.ecs_sg_id]
    cidr_blocks = ["0.0.0.0/0"]
    description     = "Allow ECS tasks to access Evidently UI via ALB on port 8000"
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["${var.my_ip}/32"]
    description = "Allows my IP access to Grafana UI"
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

resource "aws_lb_target_group" "evidently_ui" {
  name        = "${var.project_id}-evidently" # Shortened to <32 char
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
}

resource "aws_lb_target_group" "grafana" {
  name        = "${var.project_id}-grafana"
  port        = 3000
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

resource "aws_lb_listener" "evidently_ui" {
  load_balancer_arn = aws_lb.main.arn
  port              = 8000
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.evidently_ui.arn
  }
}

resource "aws_lb_listener" "grafana" {
  load_balancer_arn = aws_lb.main.arn
  port              = 3000
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.grafana.arn
  }
}
