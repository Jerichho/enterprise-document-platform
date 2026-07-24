"""Initial empty schema baseline.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-20

Domain tables (users, documents, chunks, conversations, etc.) are added in later phases.
This revision establishes Alembic version tracking and enables the pgvector extension.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Leave the extension in place; dropping it can break other schemas.
    pass
