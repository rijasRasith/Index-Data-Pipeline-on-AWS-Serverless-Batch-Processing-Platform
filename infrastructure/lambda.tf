resource "aws_cloudwatch_log_group" "lambda_validator" {
  name              = "/aws/lambda/${var.project_name}-validator"
  retention_in_days = 14
}

resource "aws_lambda_function" "validator" {
  function_name = "${var.project_name}-validator"
  role          = aws_iam_role.lambda_validator.arn
  handler       = "lambda_validator.handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size
  filename      = "${path.module}/../dist/lambda_validator.zip"

  source_code_hash = filebase64sha256("${path.module}/../dist/lambda_validator.zip")

  environment {
    variables = {
      S3_BUCKET      = aws_s3_bucket.pipeline_data.id
      GLUE_JOB_NAME  = aws_glue_job.transform.name
      LOG_LEVEL      = "INFO"
      AWS_REGION_VAR = var.aws_region
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }
}

resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.validator.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.pipeline_data.arn
  source_account = data.aws_caller_identity.current.account_id
}

resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${var.project_name}-validator-dlq"
  message_retention_seconds = 1209600
}

resource "aws_iam_role_policy" "lambda_dlq" {
  name = "${var.project_name}-lambda-dlq-policy"
  role = aws_iam_role.lambda_validator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SendToDLQ"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.lambda_dlq.arn
      }
    ]
  })
}
