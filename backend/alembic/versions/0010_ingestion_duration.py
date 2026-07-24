"""Add total ingestion duration metric on jobs.

Revision ID: 0010_ingestion_duration
Revises: 0009_latency_metrics
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_ingestion_duration"
down_revision: str | None = "0009_latency_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "duration_ms")
