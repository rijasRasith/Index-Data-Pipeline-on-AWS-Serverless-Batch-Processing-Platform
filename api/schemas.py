from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class IndexValueResponse(BaseModel):
    business_date: date
    index_level: float
    daily_return: Optional[float]
    constituent_count: int
    run_id: str
    is_current: bool


class IndexValueListResponse(BaseModel):
    data: list[IndexValueResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RunResponse(BaseModel):
    run_id: str
    business_date: date
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    file_checksum: Optional[str]
    code_version: Optional[str]
    data_quality_status: Optional[str]
    error_message: Optional[str]


class RunListResponse(BaseModel):
    data: list[RunResponse]
    total: int
    page: int
    page_size: int


class ConstituentResponse(BaseModel):
    symbol: str
    name: str
    set_version: int


class ConstituentListResponse(BaseModel):
    as_of_date: date
    constituents: list[ConstituentResponse]
    count: int


class RerunRequest(BaseModel):
    business_date: date
    force: bool = Field(default=False, description="Force rerun even if a completed run exists")


class RerunResponse(BaseModel):
    run_id: str
    business_date: date
    status: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    correlation_id: Optional[str] = None
