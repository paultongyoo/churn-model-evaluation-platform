output "image_uri" {
    value = "${aws_ecr_repository.mlflow.repository_url}:${chomp(data.local_file.image_tag.content)}"
}