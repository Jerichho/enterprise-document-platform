"""Add HNSW index for pgvector cosine similarity search.

Revision ID: 0007_chunk_embedding_hnsw
Revises: 0006_create_audit_logs
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_chunk_embedding_hnsw"
down_revision: str | None = "0006_create_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Cosine distance operator class matches RetrievalService's <=> ranking.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
