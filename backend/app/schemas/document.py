"""Document API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import DocumentFileType, IngestionJobStatus, IngestionStage, ProcessingStatus


class UploaderInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    original_filename: str
    file_type: DocumentFileType
    content_type: str
    file_size_bytes: int
    checksum_sha256: str
    uploaded_by_id: UUID
    created_at: datetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_version_id: UUID
    status: IngestionJobStatus
    attempt_number: int
    error_message: str | None
    embedding_latency_ms: int | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    duration_ms: int | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IngestionJobHistoryResponse(BaseModel):
    items: list[IngestionJobResponse]
    total: int


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    department: str
    category: str
    current_version: int
    processing_status: ProcessingStatus
    ingestion_stage: IngestionStage
    processing_error: str | None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    uploaded_by_id: UUID
    uploaded_by: UploaderInfo | None = None
    file_type: DocumentFileType | None = None
    file_size_bytes: int | None = None
    page_count: int | None = None
    chunk_count: int = 0
    embedding_count: int = 0
    created_at: datetime
    updated_at: datetime
    versions: list[DocumentVersionResponse] = Field(default_factory=list)
    latest_ingestion_job: IngestionJobResponse | None = None


class DocumentSummaryResponse(BaseModel):
    """List-item representation without nested version history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    department: str
    category: str
    current_version: int
    processing_status: ProcessingStatus
    ingestion_stage: IngestionStage
    processing_error: str | None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    uploaded_by_id: UUID
    file_type: DocumentFileType | None = None
    file_size_bytes: int | None = None
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentSummaryResponse]
    total: int
    page: int
    page_size: int


class DocumentPreviewChunk(BaseModel):
    chunk_index: int
    page_number: int | None
    content: str
    char_count: int


class DocumentPreviewResponse(BaseModel):
    document_id: UUID
    title: str
    file_type: DocumentFileType | None
    page_count: int | None
    chunk_count: int
    preview_text: str
    chunks: list[DocumentPreviewChunk]


class DocumentMetadataForm(BaseModel):
    """Validated metadata fields for multipart uploads."""

    title: str = Field(min_length=1, max_length=300)
    department: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)

    @field_validator("title", "department", "category")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be blank")
        return cleaned
