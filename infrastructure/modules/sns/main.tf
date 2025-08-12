resource "aws_sns_topic" "churn_model_alerts" {
  name = "${var.project_id}-alerts"
}

resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.churn_model_alerts.arn
  protocol  = "email"
  endpoint  = var.my_email_address
}

resource "aws_sns_topic_policy" "default" {
  arn    = aws_sns_topic.churn_model_alerts.arn
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Sid       = "AllowPublishFromLambda",
      Effect    = "Allow",
      Principal = "*",
      Action    = "SNS:Publish",
      Resource  = aws_sns_topic.churn_model_alerts.arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = var.prefect_worker_task_exec_role_arn
        }
    }
    }]
    })
}
