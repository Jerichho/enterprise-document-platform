"""Shared enumerations used by ORM models and API schemas."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Application roles for RBAC."""

    ADMIN = "admin"
    EMPLOYEE = "employee"


class DocumentFileType(StrEnum):
    """Supported upload file types."""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class ProcessingStatus(StrEnum):
    """High-level document ingestion lifecycle."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionStage(StrEnum):
    """Fine-grained ingestion pipeline stage for progress UI."""

    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionJobStatus(StrEnum):
    """Status of a single ingestion job attempt."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageRole(StrEnum):
    """Chat message author role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
