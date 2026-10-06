import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "ap-south-1"))
    s3_bucket: str = field(default_factory=lambda: os.getenv("S3_BUCKET", "index-pipeline-data"))
    s3_landing_prefix: str = "landing/"
    s3_validated_prefix: str = "validated/"
    s3_rejected_prefix: str = "rejected/"
    s3_processed_prefix: str = "processed/"
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "index_pipeline"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "pipeline"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_secret_arn: str = field(default_factory=lambda: os.getenv("DB_SECRET_ARN", ""))
    glue_job_name: str = field(default_factory=lambda: os.getenv("GLUE_JOB_NAME", "index-transform"))
    sns_topic_arn: str = field(default_factory=lambda: os.getenv("SNS_TOPIC_ARN", ""))
    api_key: str = field(default_factory=lambda: os.getenv("API_KEY", "dev-api-key"))
    api_host: str = field(default_factory=lambda: os.getenv("API_HOST", "http://localhost:8000"))
    index_base_value: float = 100.0
    index_base_date: str = "2024-01-01"
    max_missing_tolerance: float = 0.1
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )
