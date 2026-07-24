"""Search API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.ingestion.embeddings import get_embedding_provider
from app.ingestion.embeddings.base import EmbeddingProvider
from app.repositories.document_repository import DocumentRepository
from app.retrieval.service import RetrievalService
from app.schemas.search import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    TraditionalSearchResponse,
)
from app.security.dependencies import CurrentUser
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SearchService:
    return SearchService(
        db=db,
        documents=DocumentRepository(db),
        retrieval=RetrievalService(db),
        embeddings=embeddings,
        settings=settings,
    )


@router.get("", response_model=TraditionalSearchResponse)
def traditional_search(
    _current_user: CurrentUser,
    service: Annotated[SearchService, Depends(get_search_service)],
    q: Annotated[str | None, Query(description="Keyword / title search")] = None,
    department: str | None = None,
    category: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: Annotated[str, Query()] = "created_at",
    sort_order: Annotated[str, Query()] = "desc",
) -> TraditionalSearchResponse:
    """Traditional document search independent of the AI assistant."""
    if sort_order.lower() not in {"asc", "desc"}:
        sort_order = "desc"
    return service.traditional_search(
        query=q,
        department=department,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    payload: SemanticSearchRequest,
    _current_user: CurrentUser,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SemanticSearchResponse:
    """Semantic vector search over ingested document chunks."""
    return service.semantic_search(payload)
