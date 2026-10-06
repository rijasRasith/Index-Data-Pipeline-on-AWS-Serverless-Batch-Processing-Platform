import json
import os
import urllib.parse
from datetime import datetime

import boto3

from core.config import Settings
from core.constituents import CONSTITUENT_SYMBOLS
from core.logging import PipelineLogContext, generate_correlation_id, configure_logging
from core.validator import FileValidator

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
settings = Settings()
s3_client = boto3.client("s3", region_name=settings.aws_region)
glue_client = boto3.client("glue", region_name=settings.aws_region)


def read_s3_object(bucket: str, key: str) -> str:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def copy_s3_object(bucket: str, source_key: str, dest_key: str) -> None:
    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": source_key},
        Key=dest_key,
    )


def write_s3_object(bucket: str, key: str, content: str) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="application/json",
    )


def delete_s3_object(bucket: str, key: str) -> None:
    s3_client.delete_object(Bucket=bucket, Key=key)


def start_glue_job(business_date: str, file_key: str, correlation_id: str, checksum: str) -> str:
    response = glue_client.start_job_run(
        JobName=settings.glue_job_name,
        Arguments={
            "--business_date": business_date,
            "--source_file": file_key,
            "--correlation_id": correlation_id,
            "--file_checksum": checksum,
            "--s3_bucket": settings.s3_bucket,
        },
    )
    return response["JobRunId"]


def lambda_handler(event: dict, context: object) -> dict:
    correlation_id = generate_correlation_id()
    log_ctx = PipelineLogContext(
        correlation_id=correlation_id,
        business_date="unknown",
        stage="validator",
    )

    try:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        file_name = key.split("/")[-1]

        log_ctx.log_event("file_received", bucket=bucket, key=key, file_name=file_name)

        content = read_s3_object(bucket, key)
        validator = FileValidator(
            constituent_symbols=CONSTITUENT_SYMBOLS,
            missing_tolerance=settings.max_missing_tolerance,
        )
        result = validator.validate(file_name, content)

        log_ctx.business_date = str(result.business_date) if result.business_date else "unknown"
        log_ctx.log_event(
            "validation_complete",
            is_valid=result.is_valid,
            row_count=result.row_count,
            error_count=len(result.errors),
            warning_count=len(result.warnings),
            checksum=result.checksum,
        )

        if result.is_valid:
            validated_key = f"{settings.s3_validated_prefix}{file_name}"
            copy_s3_object(bucket, key, validated_key)
            delete_s3_object(bucket, key)

            log_ctx.log_event("file_validated", dest_key=validated_key)

            glue_run_id = start_glue_job(
                business_date=str(result.business_date),
                file_key=validated_key,
                correlation_id=correlation_id,
                checksum=result.checksum,
            )
            log_ctx.log_event("glue_job_started", glue_run_id=glue_run_id)

            return {
                "statusCode": 200,
                "body": {
                    "status": "validated",
                    "file": file_name,
                    "business_date": str(result.business_date),
                    "glue_run_id": glue_run_id,
                    "correlation_id": correlation_id,
                },
            }

        rejected_key = f"{settings.s3_rejected_prefix}{file_name}"
        report_key = f"{settings.s3_rejected_prefix}{file_name}.report.json"
        copy_s3_object(bucket, key, rejected_key)
        delete_s3_object(bucket, key)
        write_s3_object(bucket, report_key, json.dumps(result.to_report(), indent=2))

        log_ctx.log_event(
            "file_rejected",
            dest_key=rejected_key,
            report_key=report_key,
            errors=len(result.errors),
        )
        log_ctx.log_metrics({
            "files_rejected": 1,
            "validation_errors": len(result.errors),
        })

        return {
            "statusCode": 200,
            "body": {
                "status": "rejected",
                "file": file_name,
                "error_count": len(result.errors),
                "correlation_id": correlation_id,
            },
        }

    except Exception as exc:
        log_ctx.log_error("validation_failed", error=str(exc))
        raise
