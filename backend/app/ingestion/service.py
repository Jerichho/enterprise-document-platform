"""Document ingestion orchestration."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.ingestion.chunking import chunk_segments
from app.ingestion.embeddings.base import EmbeddingProvider
from app.ingestion.extraction import extract_text
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import IngestionJobStatus, IngestionStage, ProcessingStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.storage.base import StorageService

logger = get_logger(__name__)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite-naive and aware datetimes for duration math."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _elapsed_ms(started_at: datetime | None, completed_at: datetime) -> int | None:
    if started_at is None:
        return None
    return int((_as_utc(completed_at) - _as_utc(started_at)).total_seconds() * 1000)


class IngestionService:
    """Extract, chunk, embed, and persist document content for a job."""

    def __init__(
        self,
        documents: DocumentRepository,
        chunks: ChunkRepository,
        storage: StorageService,
        embeddings: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._storage = storage
        self._embeddings = embeddings
        self._settings = settings

    def process_job(self, job_id: UUID) -> None:
        """Run the full ingestion pipeline for a queued job."""
        claimed = self._documents.claim_ingestion_job(job_id)
        if claimed is None:
            existing = self._documents.get_ingestion_job(job_id)
            if existing is None:
                logger.error("Ingestion job %s not found", job_id)
            else:
                logger.info(
                    "Skipping ingestion job %s (status=%s); already claimed or finished",
                    job_id,
                    existing.status.value,
                )
            return

        job = claimed
        document = self._documents.get_by_id(job.document_id)
        version = self._documents.get_version(job.document_version_id)
        if document is None or version is None:
            self._fail_job(job_id, "Document or version missing for ingestion job")
            return

        logger.info(
            "Ingestion started for document %s (job %s, attempt %s)",
            document.id,
            job_id,
            job.attempt_number,
        )
        document.processing_status = ProcessingStatus.PROCESSING
        document.processing_error = None
        document.ingestion_stage = IngestionStage.EXTRACTING
        self._documents.save(document)

        try:
            data = self._storage.read(version.storage_key)

            self._set_stage(document, IngestionStage.EXTRACTING)
            segments = extract_text(data, version.file_type)

            self._set_stage(document, IngestionStage.CHUNKING)
            text_chunks = chunk_segments(
                segments,
                chunk_size=self._settings.chunk_size,
                chunk_overlap=self._settings.chunk_overlap,
            )
            if not text_chunks:
                raise AppError(
                    "No text chunks produced from document",
                    status_code=422,
                    code="empty_chunks",
                )

            self._set_stage(document, IngestionStage.EMBEDDING)
            embed_started = time.perf_counter()
            vectors = self._embeddings.embed_documents([chunk.content for chunk in text_chunks])
            embedding_latency_ms = int((time.perf_counter() - embed_started) * 1000)
            if len(vectors) != len(text_chunks):
                raise AppError(
                    "Embedding count does not match chunk count",
                    status_code=502,
                    code="embedding_count_mismatch",
                )

            provider_name = self._settings.embedding_provider
            model_name = self._settings.embedding_model

            self._set_stage(document, IngestionStage.INDEXING)
            chunk_rows = [
                DocumentChunk(
                    document_id=document.id,
                    document_version_id=version.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    char_count=chunk.char_count,
                    embedding=vector,
                )
                for chunk, vector in zip(text_chunks, vectors, strict=True)
            ]
            self._chunks.replace_version_chunks(chunk_rows)
        except Exception as exc:
            logger.exception("Ingestion failed for job %s", job_id)
            message = str(exc) if isinstance(exc, AppError) else "Ingestion failed"
            self._fail_job(job_id, message[:2000])
            return

        finished_job = self._documents.get_ingestion_job(job_id)
        document = self._documents.get_by_id(document.id)
        if finished_job is None or document is None:
            return

        finished_job.status = IngestionJobStatus.COMPLETED
        finished_job.completed_at = datetime.now(UTC)
        finished_job.error_message = None
        finished_job.embedding_latency_ms = embedding_latency_ms
        finished_job.embedding_provider = provider_name
        finished_job.embedding_model = model_name
        finished_job.duration_ms = _elapsed_ms(finished_job.started_at, finished_job.completed_at)
        self._documents.save_ingestion_job(finished_job)

        document.processing_status = ProcessingStatus.COMPLETED
        document.ingestion_stage = IngestionStage.COMPLETED
        document.processing_error = None
        document.embedding_provider = provider_name
        document.embedding_model = model_name
        self._documents.save(document)
        logger.info(
            "Ingestion completed for document %s (job %s, chunks=%s, duration_ms=%s)",
            document.id,
            job_id,
            len(chunk_rows),
            finished_job.duration_ms,
        )

    def _set_stage(self, document: Document, stage: IngestionStage) -> None:
        document.ingestion_stage = stage
        document.processing_status = ProcessingStatus.PROCESSING
        self._documents.save(document)

    def _fail_job(self, job_id: UUID, message: str) -> None:
        job = self._documents.get_ingestion_job(job_id)
        if job is None:
            return
        job.status = IngestionJobStatus.FAILED
        job.error_message = message
        job.completed_at = datetime.now(UTC)
        job.duration_ms = _elapsed_ms(job.started_at, job.completed_at)
        self._documents.save_ingestion_job(job)

        document = self._documents.get_by_id(job.document_id)
        if document is not None:
            document.processing_status = ProcessingStatus.FAILED
            document.ingestion_stage = IngestionStage.FAILED
            document.processing_error = message
            self._documents.save(document)
