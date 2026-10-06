"""Initial schema with all core tables

Revision ID: 001_initial
Revises: None
Create Date: 2024-01-15 10:00:00.000000

Rollback approach: Drop all tables in reverse dependency order.
This is safe only on a fresh database; on a populated database,
back up data before rolling back.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "securities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )

    op.create_table(
        "constituent_sets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_constituent_set_version"),
    )

    op.create_table(
        "constituent_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("constituent_set_id", sa.Integer(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["constituent_set_id"], ["constituent_sets.id"]),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("constituent_set_id", "security_id", name="uq_constituent_member"),
    )

    op.create_table(
        "daily_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("security_id", sa.Integer(), nullable=False),
        sa.Column("open_price", sa.Float(), nullable=False),
        sa.Column("high_price", sa.Float(), nullable=False),
        sa.Column("low_price", sa.Float(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_file", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["security_id"], ["securities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "security_id", name="uq_daily_price"),
    )
    op.create_index("ix_daily_price_date", "daily_prices", ["date"])
    op.create_index("ix_daily_price_security_date", "daily_prices", ["security_id", "date"])

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(50), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("file_checksum", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("code_version", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_pipeline_run_business_date", "pipeline_runs", ["business_date"])
    op.create_index("ix_pipeline_run_status", "pipeline_runs", ["status"])

    op.create_table(
        "index_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("index_level", sa.Float(), nullable=False),
        sa.Column("daily_return", sa.Float(), nullable=True),
        sa.Column("constituent_count", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(50), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_runs.run_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_index_value_date", "index_values", ["business_date"])
    op.create_index("ix_index_value_current", "index_values", ["is_current", "business_date"])
    op.create_index("ix_index_value_run", "index_values", ["run_id"])


def downgrade() -> None:
    op.drop_table("index_values")
    op.drop_table("pipeline_runs")
    op.drop_table("daily_prices")
    op.drop_table("constituent_members")
    op.drop_table("constituent_sets")
    op.drop_table("securities")
