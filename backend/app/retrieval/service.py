"""Vector similarity retrieval over document chunks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, literal, select
from sqlalchemy.orm import Session, joinedload

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import ProcessingStatus
from app.retrieval.scoring import ScoredChunk, cosine_similarity


class RetrievalService:
    """Retrieve the most relevant chunks for a query embedding.

    On PostgreSQL, ranking uses pgvector cosine distance (`<=>`) so ANN indexes
    (HNSW) can accelerate search. On SQLite (tests), falls back to in-process
    cosine similarity over JSON-stored vectors.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def similarity_search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        department: str | None = None,
        category: str | None = None,
        document_id: UUID | None = None,
        min_score: float = 0.0,
        embedding_provider: str | None = None,
    ) -> list[ScoredChunk]:
        """Return top-k chunks filtered by metadata and ranked by cosine similarity."""
        if self._uses_pgvector():
            return self._similarity_search_pgvector(
                query_embedding,
                top_k=top_k,
                department=department,
                category=category,
                document_id=document_id,
                min_score=min_score,
                embedding_provider=embedding_provider,
            )
        return self._similarity_search_python(
            query_embedding,
            top_k=top_k,
            department=department,
            category=category,
            document_id=document_id,
            min_score=min_score,
            embedding_provider=embedding_provider,
        )

    def list_completed_embedding_providers(self) -> list[tuple[str, str | None]]:
        """Return (title, embedding_provider) for completed documents."""
        rows = self._db.execute(
            select(Document.title, Document.embedding_provider).where(
                Document.processing_status == ProcessingStatus.COMPLETED,
            )
        ).all()
        return [(str(title), provider) for title, provider in rows]

    def _uses_pgvector(self) -> bool:
        bind = self._db.get_bind()
        return bind.dialect.name == "postgresql"

    def _similarity_search_pgvector(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        department: str | None,
        category: str | None,
        document_id: UUID | None,
        min_score: float,
        embedding_provider: str | None,
    ) -> list[ScoredChunk]:
        # pgvector cosine distance: 0 = identical; similarity = 1 - distance.
        distance = DocumentChunk.embedding.op("<=>")(query_embedding)
        score_expr = (literal(1.0) - distance).label("score")
        statement = (
            select(DocumentChunk, score_expr)
            .join(Document, DocumentChunk.document_id == Document.id)
            .options(joinedload(DocumentChunk.document))
            .where(Document.processing_status == ProcessingStatus.COMPLETED)
        )
        statement = self._apply_filters(
            statement,
            department=department,
            category=category,
            document_id=document_id,
            embedding_provider=embedding_provider,
        )
        if min_score > 0.0:
            statement = statement.where(score_expr >= min_score)
        statement = statement.order_by(distance).limit(top_k)

        rows = self._db.execute(statement).unique().all()
        scored: list[ScoredChunk] = []
        for chunk, score in rows:
            document = chunk.document
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=float(score),
                    document_title=document.title,
                    department=document.department,
                    category=document.category,
                )
            )
        return scored

    def _similarity_search_python(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        department: str | None,
        category: str | None,
        document_id: UUID | None,
        min_score: float,
        embedding_provider: str | None,
    ) -> list[ScoredChunk]:
        statement = self._apply_filters(
            self._base_statement(),
            department=department,
            category=category,
            document_id=document_id,
            embedding_provider=embedding_provider,
        )
        chunks = list(self._db.scalars(statement).unique().all())
        scored: list[ScoredChunk] = []
        for chunk in chunks:
            score = cosine_similarity(query_embedding, list(chunk.embedding))
            if score < min_score:
                continue
            document = chunk.document
            scored.append(
                ScoredChunk(
                    chunk=chunk,
                    score=score,
                    document_title=document.title,
                    department=document.department,
                    category=document.category,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def _base_statement(self) -> Select[tuple[DocumentChunk]]:
        return (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .options(joinedload(DocumentChunk.document))
            .where(Document.processing_status == ProcessingStatus.COMPLETED)
        )

    def _apply_filters(
        self,
        statement: Select[Any],
        *,
        department: str | None,
        category: str | None,
        document_id: UUID | None,
        embedding_provider: str | None = None,
    ) -> Select[Any]:
        if department:
            statement = statement.where(Document.department == department)
        if category:
            statement = statement.where(Document.category == category)
        if document_id:
            statement = statement.where(DocumentChunk.document_id == document_id)
        if embedding_provider:
            # Only search vectors produced by the active embedding provider.
            # Legacy rows with NULL provider are excluded once a provider is configured.
            statement = statement.where(Document.embedding_provider == embedding_provider)
        return statement
