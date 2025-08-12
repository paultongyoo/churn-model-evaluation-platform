resource "aws_s3_bucket" "bucket" {
  bucket = var.bucket_name
  force_destroy = true
}

resource "aws_s3_object" "prefixes" {
  for_each = toset([
    "data/input/",
    "data/processing/",
    "data/processed/",
    "data/errored/",
    "data/logs/"])

  bucket = aws_s3_bucket.bucket.id
  key    = each.key
  content = ""
}
