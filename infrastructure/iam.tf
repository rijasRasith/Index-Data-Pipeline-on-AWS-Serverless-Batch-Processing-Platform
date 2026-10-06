resource "aws_iam_role" "lambda_validator" {
  name = "${var.project_name}-lambda-validator"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_validator" {
  name = "${var.project_name}-lambda-validator-policy"
  role = aws_iam_role.lambda_validator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadLandingPrefix"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/landing/*"
      },
      {
        Sid    = "WriteValidatedPrefix"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:CopyObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/validated/*"
      },
      {
        Sid    = "WriteRejectedPrefix"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:CopyObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/rejected/*"
      },
      {
        Sid    = "WriteLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda_validator.arn}:*"
      },
      {
        Sid    = "StartGlueJob"
        Effect = "Allow"
        Action = [
          "glue:StartJobRun"
        ]
        Resource = "arn:aws:glue:${var.aws_region}:${data.aws_caller_identity.current.account_id}:job/${var.project_name}-transform"
      },
      {
        Sid    = "PublishMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "${var.project_name}"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role" "glue_transform" {
  name = "${var.project_name}-glue-transform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "glue_transform" {
  name = "${var.project_name}-glue-transform-policy"
  role = aws_iam_role.glue_transform.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadValidatedPrefix"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/validated/*"
      },
      {
        Sid    = "WriteProcessedPrefix"
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/processed/*"
      },
      {
        Sid    = "ReadGlueScript"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.pipeline_data.arn}/scripts/*"
      },
      {
        Sid    = "ReadDatabaseSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.db_credentials.arn
      },
      {
        Sid    = "WriteLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws-glue/*"
      },
      {
        Sid    = "PublishMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "${var.project_name}"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_transform.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}
