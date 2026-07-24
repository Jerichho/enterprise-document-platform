"""Store embedding provider metadata on documents and ingestion jobs.

Revision ID: 0011_embedding_provider_meta
Revises: 0010_ingestion_duration
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_embedding_provider_meta"
down_revision: str | None = "0010_ingestion_duration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("embedding_provider", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(length=200), nullable=True))
    op.add_column(
        "ingestion_jobs",
        sa.Column("embedding_provider", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ingestion_jobs",
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "embedding_model")
    op.drop_column("ingestion_jobs", "embedding_provider")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "embedding_provider")
