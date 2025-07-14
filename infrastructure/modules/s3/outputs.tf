output "name" {
    description = "The name of the S3 bucket"
    value       = aws_s3_bucket.bucket.bucket
}

output "bucket_arn" {
    description = "The ARN of the S3 bucket"
    value       = aws_s3_bucket.bucket.arn
}

output "bucket_id" {
    description = "The ID of the S3 bucket"
    value       = aws_s3_bucket.bucket.id
}
