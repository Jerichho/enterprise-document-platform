"""Add latency instrumentation columns for analytics.

Revision ID: 0009_latency_metrics
Revises: 0008_document_ingestion_stage
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_latency_metrics"
down_revision: str | None = "0008_document_ingestion_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("embedding_latency_ms", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("vector_search_latency_ms", sa.Integer(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("embedding_latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "embedding_latency_ms")
    op.drop_column("messages", "vector_search_latency_ms")
    op.drop_column("messages", "embedding_latency_ms")
