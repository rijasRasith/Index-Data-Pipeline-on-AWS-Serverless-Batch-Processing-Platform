import json
import sys
from datetime import date
from io import StringIO

import boto3
import pandas as pd

from core.config import Settings
from core.constituents import CONSTITUENT_SYMBOLS
from core.database import DatabaseManager
from core.index_calculator import IndexCalculator
from core.logging import PipelineLogContext, configure_logging, generate_run_id
from core.models import RunStatus


def parse_arguments(args: list[str]) -> dict:
    parsed = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                parsed[key] = args[i + 1]
                i += 2
            else:
                parsed[key] = "true"
                i += 1
        else:
            i += 1
    return parsed


def read_validated_file(s3_client: object, bucket: str, key: str) -> pd.DataFrame:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")
    df = pd.read_csv(StringIO(content))
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def standardize_types(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["symbol"] = df["symbol"].str.strip().str.upper()
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)
    if "vwap" in df.columns:
        df["vwap"] = df["vwap"].astype(float)
    return df


def write_processed_output(
    s3_client: object,
    bucket: str,
    prefix: str,
    run_id: str,
    business_date: str,
    df: pd.DataFrame,
) -> str:
    output_key = f"{prefix}{business_date}/{run_id}/prices.parquet"
    buffer = df.to_parquet(index=False)
    s3_client.put_object(Bucket=bucket, Key=output_key, Body=buffer)
    return output_key


def run_transform(args: dict) -> dict:
    configure_logging(args.get("log_level", "INFO"))
    settings = Settings()

    business_date_str = args["business_date"]
    source_file = args["source_file"]
    correlation_id = args["correlation_id"]
    file_checksum = args["file_checksum"]
    bucket = args.get("s3_bucket", settings.s3_bucket)

    business_date = date.fromisoformat(business_date_str)
    run_id = generate_run_id()

    log_ctx = PipelineLogContext(
        correlation_id=correlation_id,
        business_date=business_date_str,
        stage="transform",
    )

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    db = DatabaseManager(settings.database_url)

    session = db.get_session()
    try:
        if db.check_duplicate_run(session, business_date, file_checksum):
            log_ctx.log_event("duplicate_detected", file_checksum=file_checksum)
            return {"status": "skipped", "reason": "duplicate_file", "run_id": None}

        run = db.create_run(
            session, run_id, business_date, file_checksum, code_version="1.0.0"
        )
        db.update_run_status(session, run_id, RunStatus.TRANSFORMING)
        session.commit()

        log_ctx.log_event("transform_started", run_id=run_id, source_file=source_file)

        df = read_validated_file(s3_client, bucket, source_file)
        df = standardize_types(df)

        log_ctx.log_event("data_read", row_count=len(df), columns=list(df.columns))

        constituent_symbols = set(
            db.get_active_constituents(session, business_date) or CONSTITUENT_SYMBOLS
        )
        previous_prices = db.get_previous_prices(session, business_date)
        previous_level = db.get_previous_index_level(session, business_date)

        calculator = IndexCalculator(
            base_value=settings.index_base_value,
            base_date=settings.index_base_date,
        )
        index_result = calculator.process_price_dataframe(
            df, previous_prices, previous_level, constituent_symbols, business_date
        )

        log_ctx.log_event(
            "index_calculated",
            index_level=index_result.index_level,
            daily_return=index_result.daily_return,
            constituent_count=index_result.constituent_count,
            missing_symbols=index_result.missing_symbols,
            carried_forward=index_result.carried_forward,
        )

        prices_data = []
        for _, row in df.iterrows():
            price_row = {
                "symbol": row["symbol"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            }
            if "vwap" in row and pd.notna(row.get("vwap")):
                price_row["vwap"] = float(row["vwap"])
            prices_data.append(price_row)

        db.update_run_status(session, run_id, RunStatus.LOADING)
        session.commit()

        loaded_count = db.load_prices(session, business_date, prices_data, source_file)

        data_quality = "clean"
        if index_result.missing_symbols:
            data_quality = "missing_data"
        if index_result.carried_forward:
            data_quality = "carried_forward"

        db.save_index_value(
            session,
            business_date=business_date,
            index_level=index_result.index_level,
            daily_return=index_result.daily_return,
            constituent_count=index_result.constituent_count,
            run_id=run_id,
        )

        pipeline_run = db.get_run_by_id(session, run_id)
        if pipeline_run:
            pipeline_run.data_quality_status = data_quality
        db.update_run_status(session, run_id, RunStatus.COMPLETED)
        session.commit()

        output_key = write_processed_output(
            s3_client, bucket, settings.s3_processed_prefix,
            run_id, business_date_str, df,
        )

        log_ctx.log_event(
            "transform_complete",
            run_id=run_id,
            prices_loaded=loaded_count,
            index_level=index_result.index_level,
            output_key=output_key,
            data_quality=data_quality,
        )
        log_ctx.log_metrics({
            "rows_processed": len(df),
            "prices_loaded": loaded_count,
            "index_level": index_result.index_level,
        })

        return {
            "status": "completed",
            "run_id": run_id,
            "index_level": index_result.index_level,
            "prices_loaded": loaded_count,
            "data_quality": data_quality,
        }

    except Exception as exc:
        db.update_run_status(session, run_id, RunStatus.FAILED, error_message=str(exc))
        session.commit()
        log_ctx.log_error("transform_failed", run_id=run_id, error=str(exc))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    args = parse_arguments(sys.argv[1:])
    result = run_transform(args)
    print(json.dumps(result, indent=2))
