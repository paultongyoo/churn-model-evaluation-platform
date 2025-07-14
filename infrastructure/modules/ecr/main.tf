resource "aws_ecr_repository" "prefect" {
  name                 = "${var.project_id}-prefect"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

####### ECR Repository for MLflow Docker Image #######

resource "aws_ecr_repository" "mlflow" {
  name                 = "${var.project_id}-mlflow"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "null_resource" "build_and_push_mlflow_image" {
    triggers = {
        docker_file = md5(file("../code/mlflow/Dockerfile"))
    }

    provisioner "local-exec" {
        command = <<EOT
            set -e

            echo "Generating SHA tag..."
            IMAGE_TAG=$(git rev-parse --short HEAD)

            echo "Logging in to ECR..."
            aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.mlflow.repository_url}

            echo "Building Docker image with tag $IMAGE_TAG..."
            docker build -t ${aws_ecr_repository.mlflow.repository_url}:$IMAGE_TAG ../code/mlflow/

            echo "Pushing image to ECR with tag $IMAGE_TAG..."
            docker push ${aws_ecr_repository.mlflow.repository_url}:$IMAGE_TAG

            echo "$IMAGE_TAG" > ${path.module}/mlflow_image_tag.txt
        EOT
    }

    depends_on = [aws_ecr_repository.mlflow]
}

data "local_file" "mlflow_image_tag" {
  filename = "${path.module}/mlflow_image_tag.txt"
  depends_on = [null_resource.build_and_push_mlflow_image]
}

####### ECR Repository for S3-to-Prefect Lambda Docker Image #######

resource "aws_ecr_repository" "s3_to_prefect_lambda" {
  name                 = "${var.project_id}-s3-to-prefect-lambda"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "null_resource" "build_and_push_s3_to_prefect_lambda_image" {
    triggers = {
        docker_file = md5(file("../code/s3_to_prefect_lambda/Dockerfile"))
        force_rebuild = timestamp()  # <- this forces rebuild every apply
    }

    provisioner "local-exec" {
        command = <<EOT
            set -e

            echo "Generating SHA tag..."
            IMAGE_TAG=$(git rev-parse --short HEAD)

            echo "Logging in to ECR..."
            aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.s3_to_prefect_lambda.repository_url}

            echo "Building Docker image with tag $IMAGE_TAG..."
            DOCKER_BUILDKIT=0 docker build -t ${aws_ecr_repository.s3_to_prefect_lambda.repository_url}:$IMAGE_TAG ../code/s3_to_prefect_lambda/

            echo "Pushing image to ECR with tag $IMAGE_TAG..."
            docker push ${aws_ecr_repository.s3_to_prefect_lambda.repository_url}:$IMAGE_TAG

            echo "$IMAGE_TAG" > ${path.module}/s3_to_prefect_lambda_image_tag.txt
        EOT
    }

    depends_on = [aws_ecr_repository.s3_to_prefect_lambda]
}

data "local_file" "s3_to_prefect_lambda_image_tag" {
  filename = "${path.module}/s3_to_prefect_lambda_image_tag.txt"
  depends_on = [null_resource.build_and_push_s3_to_prefect_lambda_image]
}
