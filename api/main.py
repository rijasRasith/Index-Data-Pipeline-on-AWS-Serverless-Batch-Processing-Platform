import math
import time
from datetime import date, datetime
from typing import Optional

import boto3
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    ConstituentListResponse,
    ConstituentResponse,
    ErrorResponse,
    HealthResponse,
    IndexValueListResponse,
    IndexValueResponse,
    RerunRequest,
    RerunResponse,
    RunListResponse,
    RunResponse,
)
from core.config import Settings
from core.database import DatabaseManager
from core.logging import PipelineLogContext, configure_logging, generate_correlation_id, generate_run_id

settings = Settings()
configure_logging(settings.log_level)
db = DatabaseManager(settings.database_url)

app = FastAPI(
    title="Index Data Pipeline API",
    description="REST API for querying equal-weighted equity index values and managing pipeline runs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


@app.middleware("http")
async def log_requests(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", generate_correlation_id())
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log_ctx = PipelineLogContext(correlation_id, "api", "api")
    log_ctx.log_event(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
    )
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Response-Time-Ms"] = str(round(duration * 1000, 2))
    return response


@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/api/v1/index/latest", response_model=IndexValueResponse)
def get_latest_index_value():
    session = db.get_session()
    try:
        value = db.get_latest_index_value(session)
        if not value:
            raise HTTPException(status_code=404, detail="No index values found")
        return IndexValueResponse(
            business_date=value.business_date,
            index_level=value.index_level,
            daily_return=value.daily_return,
            constituent_count=value.constituent_count,
            run_id=value.run_id,
            is_current=value.is_current,
        )
    finally:
        session.close()


@app.get("/api/v1/index/range", response_model=IndexValueListResponse)
def get_index_values_range(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Results per page"),
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")
    session = db.get_session()
    try:
        values, total = db.get_index_values_range(session, start_date, end_date, page, page_size)
        return IndexValueListResponse(
            data=[
                IndexValueResponse(
                    business_date=v.business_date,
                    index_level=v.index_level,
                    daily_return=v.daily_return,
                    constituent_count=v.constituent_count,
                    run_id=v.run_id,
                    is_current=v.is_current,
                )
                for v in values
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total > 0 else 0,
        )
    finally:
        session.close()


@app.get("/api/v1/index/run/{run_id}", response_model=list[IndexValueResponse])
def get_index_values_by_run(run_id: str):
    session = db.get_session()
    try:
        values = db.get_index_value_by_run(session, run_id)
        if not values:
            raise HTTPException(status_code=404, detail=f"No index values found for run {run_id}")
        return [
            IndexValueResponse(
                business_date=v.business_date,
                index_level=v.index_level,
                daily_return=v.daily_return,
                constituent_count=v.constituent_count,
                run_id=v.run_id,
                is_current=v.is_current,
            )
            for v in values
        ]
    finally:
        session.close()


@app.get("/api/v1/runs", response_model=RunListResponse)
def list_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    session = db.get_session()
    try:
        runs, total = db.list_runs(session, page, page_size)
        return RunListResponse(
            data=[
                RunResponse(
                    run_id=r.run_id,
                    business_date=r.business_date,
                    status=r.status,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    file_checksum=r.file_checksum,
                    code_version=r.code_version,
                    data_quality_status=r.data_quality_status,
                    error_message=r.error_message,
                )
                for r in runs
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    finally:
        session.close()


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
def get_run_details(run_id: str):
    session = db.get_session()
    try:
        run = db.get_run_by_id(session, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return RunResponse(
            run_id=run.run_id,
            business_date=run.business_date,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            file_checksum=run.file_checksum,
            code_version=run.code_version,
            data_quality_status=run.data_quality_status,
            error_message=run.error_message,
        )
    finally:
        session.close()


@app.get("/api/v1/constituents", response_model=ConstituentListResponse)
def get_constituents(
    as_of_date: date = Query(..., description="Date to get constituents for"),
):
    session = db.get_session()
    try:
        constituents = db.get_constituents_for_date(session, as_of_date)
        return ConstituentListResponse(
            as_of_date=as_of_date,
            constituents=[
                ConstituentResponse(
                    symbol=c["symbol"],
                    name=c["name"],
                    set_version=c["set_version"],
                )
                for c in constituents
            ],
            count=len(constituents),
        )
    finally:
        session.close()


@app.post("/api/v1/rerun", response_model=RerunResponse)
def trigger_rerun(
    request: RerunRequest,
    api_key: str = Depends(verify_api_key),
):
    session = db.get_session()
    try:
        run_id = generate_run_id()
        correlation_id = generate_correlation_id()

        s3_client = boto3.client("s3", region_name=settings.aws_region)
        file_key = f"{settings.s3_validated_prefix}prices_{request.business_date.isoformat()}.csv"

        try:
            s3_client.head_object(Bucket=settings.s3_bucket, Key=file_key)
        except Exception:
            raise HTTPException(
                status_code=404,
                detail=f"No validated file found for date {request.business_date}",
            )

        glue_client = boto3.client("glue", region_name=settings.aws_region)
        glue_client.start_job_run(
            JobName=settings.glue_job_name,
            Arguments={
                "--business_date": request.business_date.isoformat(),
                "--source_file": file_key,
                "--correlation_id": correlation_id,
                "--file_checksum": "rerun",
                "--s3_bucket": settings.s3_bucket,
            },
        )

        return RerunResponse(
            run_id=run_id,
            business_date=request.business_date,
            status="initiated",
            message=f"Rerun initiated for {request.business_date}",
        )
    finally:
        session.close()
