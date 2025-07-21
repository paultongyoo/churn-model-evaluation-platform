output "churn_model_alerts_topic_arn" {
  description = "ARN of the SNS topic for churn model alerts"
  value       = aws_sns_topic.churn_model_alerts.arn
}
