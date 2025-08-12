variable "project_id" {
    description = "The project ID for the infrastructure"
    type        = string
    default     = "mlops-churn-pipeline"
}

variable "bucket_arn" {
    description = "The ARN of the S3 bucket"
    type        = string
}

variable "bucket_id" {
    description = "The ID of the S3 bucket"
    type        = string
}

variable "s3_to_prefect_lambda_image_uri" {
    description = "The URI of the S3 to Prefect Lambda image in ECR"
    type        = string
}

variable "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  type        = string
}

variable "lambda_filter_prefix" {
  description = "Prefix for S3 objects that trigger the Lambda function"
  type        = string
  default     = "data/input/"
}
