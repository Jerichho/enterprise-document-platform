"""Traditional and semantic search use cases."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.ingestion.embeddings.base import EmbeddingProvider
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.retrieval.service import RetrievalService
from app.schemas.document import DocumentSummaryResponse
from app.schemas.search import (
    SemanticHit,
    SemanticSearchRequest,
    SemanticSearchResponse,
    TraditionalSearchResponse,
)


class SearchService:
    """Document metadata/keyword search and semantic chunk retrieval."""

    def __init__(
        self,
        db: Session,
        documents: DocumentRepository,
        retrieval: RetrievalService,
        embeddings: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._db = db
        self._documents = documents
        self._retrieval = retrieval
        self._embeddings = embeddings
        self._settings = settings

    def traditional_search(
        self,
        *,
        query: str | None = None,
        department: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> TraditionalSearchResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        if query and query.strip():
            return self._keyword_search(
                query=query.strip(),
                department=department,
                category=category,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )

        items, total = self._documents.list_documents(
            page=page,
            page_size=page_size,
            department=department,
            category=category,
            title_query=None,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return TraditionalSearchResponse(
            items=[DocumentSummaryResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            query=query,
        )

    def semantic_search(self, payload: SemanticSearchRequest) -> SemanticSearchResponse:
        top_k = payload.top_k or self._settings.retrieval_top_k
        query_embedding = self._embeddings.embed_query(payload.query)
        # Retrieve without min_score filter first so the client can inspect scores.
        hits = self._retrieval.similarity_search(
            query_embedding,
            top_k=top_k,
            department=payload.department,
            category=payload.category,
            document_id=payload.document_id,
            min_score=0.0,
            embedding_provider=self._settings.embedding_provider,
        )
        max_score = max((hit.score for hit in hits), default=None)
        insufficient = not hits or (
            max_score is not None and max_score < self._settings.retrieval_min_score
        )
        return SemanticSearchResponse(
            query=payload.query,
            hits=[
                SemanticHit(
                    chunk_id=hit.chunk.id,
                    document_id=hit.chunk.document_id,
                    document_title=hit.document_title,
                    department=hit.department,
                    category=hit.category,
                    page_number=hit.chunk.page_number,
                    chunk_index=hit.chunk.chunk_index,
                    relevance_score=round(hit.score, 6),
                    content=hit.chunk.content,
                )
                for hit in hits
            ],
            max_score=None if max_score is None else round(max_score, 6),
            insufficient_context=insufficient,
        )

    def _keyword_search(
        self,
        *,
        query: str,
        department: str | None,
        category: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> TraditionalSearchResponse:
        pattern = f"%{query}%"
        filters = [
            or_(
                Document.title.ilike(pattern),
                Document.department.ilike(pattern),
                Document.category.ilike(pattern),
                DocumentChunk.content.ilike(pattern),
            )
        ]
        if department:
            filters.append(Document.department == department)
        if category:
            filters.append(Document.category == category)

        sort_columns = {
            "created_at": Document.created_at,
            "updated_at": Document.updated_at,
            "title": Document.title,
            "department": Document.department,
            "category": Document.category,
        }
        sort_column = sort_columns.get(sort_by, Document.created_at)
        order = sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc()

        statement = (
            select(Document)
            .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(*filters)
            .distinct()
            .order_by(order)
        )
        all_items = list(self._db.scalars(statement).unique().all())
        total = len(all_items)
        start = (page - 1) * page_size
        page_items = all_items[start : start + page_size]
        return TraditionalSearchResponse(
            items=[DocumentSummaryResponse.model_validate(item) for item in page_items],
            total=total,
            page=page,
            page_size=page_size,
            query=query,
        )
