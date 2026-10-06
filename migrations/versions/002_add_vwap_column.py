"""Add VWAP column to daily_prices for volume-weighted average price

Revision ID: 002_add_vwap
Revises: 001_initial
Create Date: 2024-01-22 10:00:00.000000

Schema evolution: The input file contract now tolerates an optional 'vwap' column.
The validator passes it through, the Glue job maps it, and this migration adds the
database column. Old rows without VWAP data remain valid with NULL values.

Rollback approach: Drop the vwap column. Existing data in this column will be lost,
but all other data remains intact since the column is nullable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_add_vwap"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("daily_prices", sa.Column("vwap", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_prices", "vwap")
