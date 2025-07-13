resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
  force_destroy = true
}
