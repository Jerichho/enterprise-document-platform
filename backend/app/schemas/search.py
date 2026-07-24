"""Search and conversation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MessageRole
from app.schemas.document import DocumentSummaryResponse


class TraditionalSearchResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    page: int
    page_size: int
    query: str | None = None


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    department: str | None = None
    category: str | None = None
    document_id: UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be blank")
        return cleaned


class SemanticHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    department: str
    category: str
    page_number: int | None
    chunk_index: int
    relevance_score: float
    content: str


class SemanticSearchResponse(BaseModel):
    query: str
    hits: list[SemanticHit]
    max_score: float | None
    insufficient_context: bool


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_id: UUID | None
    document_id: UUID | None
    document_title: str
    page_number: int | None
    chunk_index: int | None
    relevance_score: float
    rank: int
    snippet: str


class RetrievalMeta(BaseModel):
    """Technical retrieval stats — not part of the primary answer text."""

    max_relevance: float | None = None
    chunks_retrieved: int = 0
    supporting_chunks: int = 0
    retrieval_latency_ms: int | None = None
    embedding_latency_ms: int | None = None
    llm_latency_ms: int | None = None
    min_relevance_threshold: float | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    content: str
    retrieval_top_k: int | None = None
    retrieval_min_score: float | None = None
    max_retrieval_score: float | None = None
    grounded: bool | None = None
    insufficient_context: bool | None = None
    answer_status: Literal["grounded", "insufficient_context", "demo"] | None = None
    suggestion: str | None = None
    embedding_latency_ms: int | None = None
    vector_search_latency_ms: int | None = None
    llm_latency_ms: int | None = None
    llm_model: str | None = None
    created_at: datetime
    citations: list[CitationResponse] = Field(default_factory=list)
    retrieval: RetrievalMeta | None = None
    embedding_provider_mismatch: bool = False
    mismatched_documents: list[str] = Field(default_factory=list)


class ConversationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    total: int


class AskMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    department: str | None = None
    category: str | None = None
    document_id: UUID | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be blank")
        return cleaned


class AskMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
