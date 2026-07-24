"""Document management API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import write_audit
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.ingestion.embeddings import get_embedding_provider
from app.ingestion.embeddings.base import EmbeddingProvider
from app.ingestion.runner import process_ingestion_job
from app.models.enums import ProcessingStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import (
    DocumentListResponse,
    DocumentMetadataForm,
    DocumentPreviewResponse,
    DocumentResponse,
    IngestionJobHistoryResponse,
)
from app.security.dependencies import CurrentUser, RequireAdmin
from app.services.document_service import DocumentService
from app.storage.base import StorageService
from app.storage.factory import get_storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> DocumentService:
    return DocumentService(
        DocumentRepository(db),
        storage,
        settings,
        chunks=ChunkRepository(db),
        embeddings=embeddings,
    )


def _schedule_ingestion(
    background_tasks: BackgroundTasks,
    settings: Settings,
    job_id: UUID,
) -> None:
    if settings.app_env == "test":
        # DocumentService already processed inline for the request-scoped DB.
        return
    background_tasks.add_task(process_ingestion_job, job_id)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    admin: RequireAdmin,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()],
    department: Annotated[str, Form()],
    category: Annotated[str, Form()],
) -> DocumentResponse:
    """Upload a PDF, DOCX, or TXT document (admin only)."""
    metadata = DocumentMetadataForm(title=title, department=department, category=category)
    data = await file.read()
    document, job_id = service.upload(
        metadata=metadata,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        uploader=admin,
    )
    write_audit(
        db,
        request,
        action="document.upload",
        actor_user_id=admin.id,
        resource_type="document",
        resource_id=document.id,
        details={"title": document.title, "department": document.department},
    )
    _schedule_ingestion(background_tasks, settings, job_id)
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    department: str | None = None,
    category: str | None = None,
    status_filter: Annotated[ProcessingStatus | None, Query(alias="status")] = None,
    q: Annotated[
        str | None,
        Query(description="Keyword search over title, department, category, and chunk text"),
    ] = None,
    sort_by: Annotated[str, Query()] = "created_at",
    sort_order: Annotated[str, Query()] = "desc",
) -> DocumentListResponse:
    """List documents with filters and pagination (authenticated users)."""
    if sort_order.lower() not in {"asc", "desc"}:
        sort_order = "desc"
    return service.list_documents(
        viewer=current_user,
        page=page,
        page_size=page_size,
        department=department,
        category=category,
        status=status_filter,
        title_query=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    """Fetch document details including versions and latest ingestion job."""
    return service.get_document(document_id, viewer=current_user)


@router.get("/{document_id}/ingestion-jobs", response_model=IngestionJobHistoryResponse)
def list_document_ingestion_jobs(
    document_id: UUID,
    current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> IngestionJobHistoryResponse:
    """List ingestion attempts for a document (error details admin-only)."""
    items = service.list_ingestion_jobs(document_id, viewer=current_user)
    return IngestionJobHistoryResponse(items=items, total=len(items))


@router.get("/{document_id}/preview", response_model=DocumentPreviewResponse)
def preview_document(
    document_id: UUID,
    _current_user: CurrentUser,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentPreviewResponse:
    """Return extracted text preview and chunk excerpts for an authorized viewer."""
    return service.get_preview(document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    request: Request,
    document_id: UUID,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> None:
    """Delete a document, its versions, jobs, and stored files (admin only)."""
    service.delete_document(document_id)
    write_audit(
        db,
        request,
        action="document.delete",
        actor_user_id=admin.id,
        resource_type="document",
        resource_id=document_id,
    )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(
    request: Request,
    document_id: UUID,
    background_tasks: BackgroundTasks,
    admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    """Queue the current document version for ingestion again (admin only)."""
    document, job_id = service.reprocess(document_id, viewer=admin)
    write_audit(
        db,
        request,
        action="document.reprocess",
        actor_user_id=admin.id,
        resource_type="document",
        resource_id=document_id,
        details={"job_id": str(job_id)},
    )
    _schedule_ingestion(background_tasks, settings, job_id)
    return document
