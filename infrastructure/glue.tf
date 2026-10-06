resource "aws_glue_job" "transform" {
  name     = "${var.project_name}-transform"
  role_arn = aws_iam_role.glue_transform.arn

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.pipeline_data.id}/scripts/transform.py"
    python_version  = "3.9"
  }

  max_capacity = var.glue_max_capacity
  max_retries  = 1
  timeout      = 10

  default_arguments = {
    "--job-language"        = "python"
    "--TempDir"             = "s3://${aws_s3_bucket.pipeline_data.id}/tmp/"
    "--enable-metrics"      = "true"
    "--DB_SECRET_ARN"       = aws_secretsmanager_secret.db_credentials.arn
    "--S3_BUCKET"           = aws_s3_bucket.pipeline_data.id
    "--additional-python-modules" = "psycopg2-binary,sqlalchemy,structlog,pandas"
  }
}
