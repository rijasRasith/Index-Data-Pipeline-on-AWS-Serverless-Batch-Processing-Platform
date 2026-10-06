variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "index-pipeline"
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "index_pipeline"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "pipeline"
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "glue_max_capacity" {
  description = "Glue job maximum DPU capacity (Python Shell minimum is 0.0625)"
  type        = number
  default     = 0.0625
}

variable "alert_email" {
  description = "Email address for alarm notifications"
  type        = string
  default     = ""
}

variable "budget_limit" {
  description = "Monthly budget limit in USD"
  type        = string
  default     = "20"
}
