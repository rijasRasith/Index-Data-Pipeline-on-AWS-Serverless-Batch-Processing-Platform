"""Add data quality status and turnover ratio columns

Revision ID: 003_quality_turnover
Revises: 002_add_vwap
Create Date: 2024-01-29 10:00:00.000000

Schema evolution: Adds a data_quality_status column to pipeline_runs to record
whether a run had clean data, missing symbols, or carried-forward prices.
Also adds turnover_ratio to index_values for future analytics.

Rollback approach: Drop both columns. Data quality status metadata will be lost
but pipeline functionality is unaffected since these columns are informational.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_quality_turnover"
down_revision: Union[str, None] = "002_add_vwap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("data_quality_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "index_values",
        sa.Column("turnover_ratio", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("index_values", "turnover_ratio")
    op.drop_column("pipeline_runs", "data_quality_status")
