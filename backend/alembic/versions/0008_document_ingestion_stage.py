"""Add ingestion_stage column for pipeline progress tracking.

Revision ID: 0008_document_ingestion_stage
Revises: 0007_chunk_embedding_hnsw
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_document_ingestion_stage"
down_revision: str | None = "0007_chunk_embedding_hnsw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "ingestion_stage",
            sa.String(length=32),
            nullable=False,
            server_default="uploaded",
        ),
    )
    op.create_index("ix_documents_ingestion_stage", "documents", ["ingestion_stage"])
    # Align existing rows with their high-level processing status.
    op.execute(
        """
        UPDATE documents
        SET ingestion_stage = CASE processing_status
            WHEN 'completed' THEN 'completed'
            WHEN 'failed' THEN 'failed'
            WHEN 'processing' THEN 'extracting'
            ELSE 'uploaded'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_documents_ingestion_stage", table_name="documents")
    op.drop_column("documents", "ingestion_stage")
