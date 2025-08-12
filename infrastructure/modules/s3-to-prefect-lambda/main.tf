
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_id}-lambda-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Effect = "Allow",
      Sid    = ""
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_exec" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "prefect_trigger" {
    function_name = "${var.project_id}-trigger"
    role          = aws_iam_role.lambda_exec.arn
    timeout       = 60
    package_type    = "Image"
    image_uri       = var.s3_to_prefect_lambda_image_uri

  environment {
    variables = {
      PREFECT_API_URL = "http://${var.alb_dns_name}:4200/api"
    }
  }
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.prefect_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.bucket_arn
}

# See Makefile for the lambda filter prefix
resource "aws_s3_bucket_notification" "s3_to_lambda" {
  bucket = var.bucket_id

  lambda_function {
    lambda_function_arn = aws_lambda_function.prefect_trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = var.lambda_filter_prefix
  }

  depends_on = [aws_lambda_permission.allow_s3]
}
