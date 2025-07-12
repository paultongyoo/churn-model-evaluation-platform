resource "aws_ecr_repository" "mlflow" {
  name                 = "${var.project_id}-mlflow"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "null_resource" "build_and_push_mlflow_image" {
    triggers = {
        docker_file = md5(file(var.mlflow_dockerfile_local_path))
    }

    provisioner "local-exec" {
        command = <<EOT
            set -e

            echo "Generating SHA tag..."
            IMAGE_TAG=$(git rev-parse --short HEAD)

            echo "Logging in to ECR..."
            aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.mlflow.repository_url}

            echo "Building Docker image with tag $IMAGE_TAG..."
            docker build -t mlflow-local ../docker/mlflow/
            docker tag mlflow-local:latest ${aws_ecr_repository.mlflow.repository_url}:$IMAGE_TAG

            echo "Pushing image to ECR with tag $IMAGE_TAG..."
            docker push ${aws_ecr_repository.mlflow.repository_url}:$IMAGE_TAG

            echo "$IMAGE_TAG" > ${path.module}/ecr_image_tag.txt
        EOT
    }

    depends_on = [aws_ecr_repository.mlflow]
}

data "local_file" "image_tag" {
  filename = "${path.module}/ecr_image_tag.txt"
  depends_on = [null_resource.build_and_push_mlflow_image]
}