output "s3_bucket_name" {
  description = "S3 bucket name for pipeline data"
  value       = aws_s3_bucket.pipeline_data.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.pipeline_data.arn
}

output "lambda_function_name" {
  description = "Lambda validator function name"
  value       = aws_lambda_function.validator.function_name
}

output "lambda_function_arn" {
  description = "Lambda validator function ARN"
  value       = aws_lambda_function.validator.arn
}

output "glue_job_name" {
  description = "Glue transform job name"
  value       = aws_glue_job.transform.name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.pipeline.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL address (hostname only)"
  value       = aws_db_instance.pipeline.address
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "sns_topic_arn" {
  description = "SNS topic ARN for pipeline alerts"
  value       = aws_sns_topic.pipeline_alerts.arn
}

output "dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.pipeline.dashboard_name}"
}

output "dlq_url" {
  description = "Dead letter queue URL for Lambda"
  value       = aws_sqs_queue.lambda_dlq.url
}
