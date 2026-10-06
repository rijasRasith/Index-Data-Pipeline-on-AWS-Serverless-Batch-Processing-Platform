from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index as SqlIndex,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class RunStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    TRANSFORMING = "transforming"
    LOADING = "loading"
    COMPLETED = "completed"
    FAILED = "failed"


class Security(Base):
    __tablename__ = "securities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    isin = Column(String(12), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    prices = relationship("DailyPrice", back_populates="security")


class ConstituentSet(Base):
    __tablename__ = "constituent_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("version", name="uq_constituent_set_version"),
    )

    members = relationship("ConstituentMember", back_populates="constituent_set")


class ConstituentMember(Base):
    __tablename__ = "constituent_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    constituent_set_id = Column(
        Integer, ForeignKey("constituent_sets.id"), nullable=False
    )
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "constituent_set_id", "security_id", name="uq_constituent_member"
        ),
    )

    constituent_set = relationship("ConstituentSet", back_populates="members")
    security = relationship("Security")


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False, default=0)
    vwap = Column(Float, nullable=True)
    source_file = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("date", "security_id", name="uq_daily_price"),
        SqlIndex("ix_daily_price_date", "date"),
        SqlIndex("ix_daily_price_security_date", "security_id", "date"),
    )

    security = relationship("Security", back_populates="prices")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), unique=True, nullable=False)
    business_date = Column(Date, nullable=False)
    file_checksum = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default=RunStatus.PENDING.value)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    code_version = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    data_quality_status = Column(String(20), nullable=True)

    __table_args__ = (
        SqlIndex("ix_pipeline_run_business_date", "business_date"),
        SqlIndex("ix_pipeline_run_status", "status"),
    )

    index_values = relationship("IndexValue", back_populates="pipeline_run")


class IndexValue(Base):
    __tablename__ = "index_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_date = Column(Date, nullable=False)
    index_level = Column(Float, nullable=False)
    daily_return = Column(Float, nullable=True)
    constituent_count = Column(Integer, nullable=False)
    run_id = Column(String(50), ForeignKey("pipeline_runs.run_id"), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True)
    turnover_ratio = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        SqlIndex("ix_index_value_date", "business_date"),
        SqlIndex("ix_index_value_current", "is_current", "business_date"),
        SqlIndex("ix_index_value_run", "run_id"),
    )

    pipeline_run = relationship("PipelineRun", back_populates="index_values")
