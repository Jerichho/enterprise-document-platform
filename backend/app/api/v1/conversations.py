"""Conversation and RAG chat API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.ingestion.embeddings import get_embedding_provider
from app.ingestion.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.repositories.conversation_repository import ConversationRepository
from app.retrieval.service import RetrievalService
from app.schemas.search import (
    AskMessageRequest,
    AskMessageResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
)
from app.security.dependencies import CurrentUser
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> ConversationService:
    return ConversationService(
        conversations=ConversationRepository(db),
        retrieval=RetrievalService(db),
        embeddings=embeddings,
        llm=llm,
        settings=settings,
    )


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: CurrentUser,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationSummary:
    return service.create(current_user, payload)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    current_user: CurrentUser,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListResponse:
    return service.list_conversations(current_user, page=page, page_size=page_size)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationDetail:
    return service.get_conversation(conversation_id, current_user)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> None:
    service.delete_conversation(conversation_id, current_user)


@router.post("/{conversation_id}/messages", response_model=AskMessageResponse)
def ask_message(
    conversation_id: UUID,
    payload: AskMessageRequest,
    current_user: CurrentUser,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> AskMessageResponse:
    """Ask a question and receive a grounded answer with citations."""
    return service.ask(conversation_id, current_user, payload)
