"""Persistence helpers for document chunks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk


class ChunkRepository:
    """Data-access helpers for embedded document chunks."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def replace_version_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Delete existing chunks for the version, then insert the provided set."""
        if not chunks:
            return []
        version_id = chunks[0].document_version_id
        self._db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_version_id == version_id)
        )
        self._db.add_all(chunks)
        self._db.commit()
        for chunk in chunks:
            self._db.refresh(chunk)
        return chunks

    def delete_for_version(self, document_version_id: UUID) -> int:
        result = self._db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_version_id == document_version_id)
        )
        self._db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def list_for_document(self, document_id: UUID) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self._db.scalars(statement).all())

    def count_for_version(self, document_version_id: UUID) -> int:
        from sqlalchemy import func

        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_version_id == document_version_id)
        )
        return int(self._db.scalar(statement) or 0)

    def count_for_document(self, document_id: UUID) -> int:
        from sqlalchemy import func

        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        return int(self._db.scalar(statement) or 0)

    def page_count_for_document(self, document_id: UUID) -> int | None:
        from sqlalchemy import func

        statement = select(func.max(DocumentChunk.page_number)).where(
            DocumentChunk.document_id == document_id
        )
        value = self._db.scalar(statement)
        return int(value) if value is not None else None
