resource "aws_sns_topic" "pipeline_alerts" {
  name = "${var.project_name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda validator function errors detected"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.validator.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "glue_failure" {
  alarm_name          = "${var.project_name}-glue-failure"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "glue.driver.aggregate.numFailedTasks"
  namespace           = "AWS/Glue"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Glue transform job failure detected"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]

  dimensions = {
    JobName = aws_glue_job.transform.name
  }
}

resource "aws_cloudwatch_metric_alarm" "rejected_files" {
  alarm_name          = "${var.project_name}-rejected-files"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "files_rejected"
  namespace           = var.project_name
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "One or more price files were rejected by validation"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "missing_data" {
  alarm_name          = "${var.project_name}-missing-data"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "files_received"
  namespace           = var.project_name
  period              = 86400
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "No price file arrived by the expected deadline on a business day"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "pipeline_duration" {
  alarm_name          = "${var.project_name}-pipeline-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "pipeline_duration_seconds"
  namespace           = var.project_name
  period              = 300
  statistic           = "Maximum"
  threshold           = 300
  alarm_description   = "Pipeline execution time exceeded 5 minutes"
  alarm_actions       = [aws_sns_topic.pipeline_alerts.arn]
}

resource "aws_cloudwatch_dashboard" "pipeline" {
  dashboard_name = "${var.project_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Files Processed"
          metrics = [
            [var.project_name, "files_received", { stat = "Sum", period = 86400 }],
            [var.project_name, "files_rejected", { stat = "Sum", period = 86400 }]
          ]
          region = var.aws_region
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "Lambda Validator"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.validator.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.validator.function_name],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.validator.function_name]
          ]
          region = var.aws_region
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Index Values"
          metrics = [
            [var.project_name, "index_level", { stat = "Average", period = 86400 }],
            [var.project_name, "rows_processed", { stat = "Sum", period = 86400 }]
          ]
          region = var.aws_region
          period = 86400
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "Pipeline Duration"
          metrics = [
            [var.project_name, "pipeline_duration_seconds", { stat = "Maximum", period = 300 }]
          ]
          region = var.aws_region
          period = 300
        }
      }
    ]
  })
}
