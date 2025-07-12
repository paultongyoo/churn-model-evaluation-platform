output "image_uri" {
    value = "${aws_ecr_repository.mlflow.repository_url}:latest"
}