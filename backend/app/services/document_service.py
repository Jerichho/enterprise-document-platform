"""Document management use cases."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.ingestion.embeddings.base import EmbeddingProvider
from app.ingestion.service import IngestionService
from app.models.document import Document, DocumentVersion
from app.models.enums import IngestionStage, ProcessingStatus, UserRole
from app.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentListResponse,
    DocumentMetadataForm,
    DocumentPreviewChunk,
    DocumentPreviewResponse,
    DocumentResponse,
    DocumentSummaryResponse,
    IngestionJobResponse,
)
from app.services.file_validation import ValidatedUpload, validate_upload
from app.storage.base import StorageService

logger = get_logger(__name__)

PREVIEW_MAX_CHARS = 12_000


class DocumentService:
    """Upload, list, inspect, delete, and requeue documents for ingestion."""

    def __init__(
        self,
        documents: DocumentRepository,
        storage: StorageService,
        settings: Settings,
        *,
        chunks: ChunkRepository | None = None,
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._settings = settings
        self._chunks = chunks
        self._embeddings = embeddings

    def upload(
        self,
        *,
        metadata: DocumentMetadataForm,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        uploader: User,
    ) -> tuple[DocumentResponse, UUID]:
        """Create a document and queue ingestion. Returns (response, job_id)."""
        validated = validate_upload(
            filename=filename,
            content_type=content_type,
            data=data,
            settings=self._settings,
        )
        storage_key = self._build_storage_key(validated)

        try:
            self._storage.save(
                key=storage_key,
                data=validated.data,
                content_type=validated.content_type,
            )
        except Exception as exc:
            logger.exception("Failed to store uploaded file")
            raise AppError(
                "Failed to store uploaded file",
                status_code=500,
                code="storage_error",
            ) from exc

        document = Document(
            title=metadata.title,
            department=metadata.department,
            category=metadata.category,
            current_version=1,
            processing_status=ProcessingStatus.PENDING,
            ingestion_stage=IngestionStage.UPLOADED,
            uploaded_by_id=uploader.id,
        )
        version = DocumentVersion(
            version_number=1,
            storage_key=storage_key,
            original_filename=validated.original_filename,
            file_type=validated.file_type,
            content_type=validated.content_type,
            file_size_bytes=validated.size_bytes,
            checksum_sha256=validated.checksum_sha256,
            uploaded_by_id=uploader.id,
        )
        document.versions.append(version)

        try:
            saved = self._documents.add_document(document)
            current_version = self._documents.get_current_version(saved)
            if current_version is None:
                raise AppError(
                    "Failed to save document version",
                    status_code=500,
                    code="document_persist_error",
                )
            job = self._documents.create_ingestion_job(
                document_id=saved.id,
                document_version_id=current_version.id,
                attempt_number=1,
            )
        except AppError:
            self._storage.delete(storage_key)
            raise
        except Exception as exc:
            self._storage.delete(storage_key)
            logger.exception("Failed to persist document metadata")
            raise AppError(
                "Failed to save document metadata",
                status_code=500,
                code="document_persist_error",
            ) from exc

        self._maybe_process_inline(job.id)
        return self.get_document(saved.id, viewer=uploader), job.id

    def list_documents(
        self,
        *,
        viewer: User,
        page: int = 1,
        page_size: int = 20,
        department: str | None = None,
        category: str | None = None,
        status: ProcessingStatus | None = None,
        title_query: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> DocumentListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        items, total = self._documents.list_documents(
            page=page,
            page_size=page_size,
            department=department,
            category=category,
            status=status,
            title_query=title_query,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return DocumentListResponse(
            items=[self._to_summary(item, viewer=viewer) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_document(self, document_id: UUID, *, viewer: User | None = None) -> DocumentResponse:
        document = self._documents.get_by_id(document_id, with_details=True)
        if document is None:
            raise AppError("Document not found", status_code=404, code="document_not_found")
        return self._to_detail(document, viewer=viewer)

    def get_preview(self, document_id: UUID) -> DocumentPreviewResponse:
        document = self._documents.get_by_id(document_id, with_details=True)
        if document is None:
            raise AppError("Document not found", status_code=404, code="document_not_found")
        if self._chunks is None:
            raise AppError(
                "Preview unavailable",
                status_code=503,
                code="preview_unavailable",
            )

        chunks = self._chunks.list_for_document(document.id)
        preview_parts: list[str] = []
        remaining = PREVIEW_MAX_CHARS
        for chunk in chunks:
            if remaining <= 0:
                break
            excerpt = chunk.content[:remaining]
            preview_parts.append(excerpt)
            remaining -= len(excerpt)

        current = self._documents.get_current_version(document)
        page_count = self._chunks.page_count_for_document(document.id)
        return DocumentPreviewResponse(
            document_id=document.id,
            title=document.title,
            file_type=current.file_type if current else None,
            page_count=page_count,
            chunk_count=len(chunks),
            preview_text="\n\n".join(preview_parts),
            chunks=[
                DocumentPreviewChunk(
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    char_count=chunk.char_count,
                )
                for chunk in chunks[:50]
            ],
        )

    def delete_document(self, document_id: UUID) -> None:
        document = self._documents.get_by_id(document_id, with_details=True)
        if document is None:
            raise AppError("Document not found", status_code=404, code="document_not_found")

        storage_keys = [version.storage_key for version in document.versions]
        self._documents.delete(document)
        for key in storage_keys:
            try:
                self._storage.delete(key)
            except Exception:
                logger.exception("Failed to delete storage object %s", key)

    def reprocess(self, document_id: UUID, *, viewer: User) -> tuple[DocumentResponse, UUID]:
        """Queue the current version for ingestion again. Returns (response, job_id)."""
        document = self._documents.get_by_id(document_id, with_details=True)
        if document is None:
            raise AppError("Document not found", status_code=404, code="document_not_found")

        if document.processing_status == ProcessingStatus.PROCESSING:
            raise AppError(
                "Document is already processing",
                status_code=409,
                code="already_processing",
            )

        if self._documents.has_active_ingestion_job(document.id):
            raise AppError(
                "An ingestion job is already pending or running for this document",
                status_code=409,
                code="duplicate_ingestion_job",
            )

        current_version = self._documents.get_current_version(document)
        if current_version is None:
            raise AppError(
                "Document has no current version to reprocess",
                status_code=409,
                code="missing_version",
            )

        attempt = self._documents.next_attempt_number(document.id)
        document.processing_status = ProcessingStatus.PENDING
        document.ingestion_stage = IngestionStage.UPLOADED
        document.processing_error = None
        self._documents.save(document)
        job = self._documents.create_ingestion_job(
            document_id=document.id,
            document_version_id=current_version.id,
            attempt_number=attempt,
        )
        self._maybe_process_inline(job.id)
        return self.get_document(document.id, viewer=viewer), job.id

    def list_ingestion_jobs(
        self,
        document_id: UUID,
        *,
        viewer: User,
    ) -> list[IngestionJobResponse]:
        """Return attempt history for a document (admin sees error details)."""
        document = self._documents.get_by_id(document_id)
        if document is None:
            raise AppError("Document not found", status_code=404, code="document_not_found")

        jobs = self._documents.list_ingestion_jobs_for_document(document_id)
        items: list[IngestionJobResponse] = []
        for job in jobs:
            item = IngestionJobResponse.model_validate(job)
            if viewer.role != UserRole.ADMIN:
                item.error_message = None
            items.append(item)
        return items

    def _to_summary(self, document: Document, *, viewer: User) -> DocumentSummaryResponse:
        current = self._current_version(document)
        chunk_count = self._chunk_count(document.id)
        response = DocumentSummaryResponse(
            id=document.id,
            title=document.title,
            department=document.department,
            category=document.category,
            current_version=document.current_version,
            processing_status=document.processing_status,
            ingestion_stage=document.ingestion_stage,
            processing_error=self._error_for_viewer(document.processing_error, viewer),
            embedding_provider=document.embedding_provider,
            embedding_model=document.embedding_model,
            uploaded_by_id=document.uploaded_by_id,
            file_type=current.file_type if current else None,
            file_size_bytes=current.file_size_bytes if current else None,
            chunk_count=chunk_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        return response

    def _to_detail(self, document: Document, *, viewer: User | None) -> DocumentResponse:
        current = self._current_version(document)
        chunk_count = self._chunk_count(document.id)
        page_count = None
        if self._chunks is not None:
            page_count = self._chunks.page_count_for_document(document.id)

        latest_job = self._documents.latest_ingestion_job(document.id)
        response = DocumentResponse.model_validate(document)
        response.processing_error = self._error_for_viewer(document.processing_error, viewer)
        response.file_type = current.file_type if current else None
        response.file_size_bytes = current.file_size_bytes if current else None
        response.page_count = page_count
        response.chunk_count = chunk_count
        response.embedding_count = chunk_count
        if latest_job is not None:
            job = IngestionJobResponse.model_validate(latest_job)
            if viewer is None or viewer.role != UserRole.ADMIN:
                job.error_message = None
            response.latest_ingestion_job = job
        return response

    def _current_version(self, document: Document) -> DocumentVersion | None:
        if document.versions:
            for version in document.versions:
                if version.version_number == document.current_version:
                    return version
            return document.versions[-1]
        return self._documents.get_current_version(document)

    def _chunk_count(self, document_id: UUID) -> int:
        if self._chunks is None:
            return 0
        return self._chunks.count_for_document(document_id)

    def _error_for_viewer(self, error: str | None, viewer: User | None) -> str | None:
        if error is None:
            return None
        if viewer is not None and viewer.role == UserRole.ADMIN:
            return error
        return None

    def _maybe_process_inline(self, job_id: UUID) -> None:
        """In test mode, run ingestion immediately with the request-scoped session."""
        if self._settings.app_env != "test":
            return
        if self._chunks is None or self._embeddings is None:
            logger.warning("Skipping inline ingestion; chunk/embedding deps missing")
            return
        IngestionService(
            documents=self._documents,
            chunks=self._chunks,
            storage=self._storage,
            embeddings=self._embeddings,
            settings=self._settings,
        ).process_job(job_id)

    def _build_storage_key(self, validated: ValidatedUpload) -> str:
        return f"documents/{uuid4()}/{validated.safe_filename}"
