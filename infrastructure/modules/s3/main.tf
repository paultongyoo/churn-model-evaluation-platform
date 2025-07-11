resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
  force_destroy = true
}

output "name" {
    description = "The name of the S3 bucket"
    value       = aws_s3_bucket.bucket.bucket
}