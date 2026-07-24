"""Document persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, selectinload

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentVersion, IngestionJob
from app.models.enums import IngestionJobStatus, IngestionStage, ProcessingStatus


class DocumentRepository:
    """Data-access helpers for documents, versions, and ingestion jobs."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, document_id: UUID, *, with_details: bool = False) -> Document | None:
        statement: Select[tuple[Document]] = select(Document).where(Document.id == document_id)
        if with_details:
            statement = statement.options(
                selectinload(Document.versions),
                selectinload(Document.ingestion_jobs),
                selectinload(Document.uploaded_by),
            )
        else:
            statement = statement.options(selectinload(Document.uploaded_by))
        return self._db.scalar(statement)

    def get_version(self, version_id: UUID) -> DocumentVersion | None:
        return self._db.get(DocumentVersion, version_id)

    def get_ingestion_job(self, job_id: UUID) -> IngestionJob | None:
        return self._db.get(IngestionJob, job_id)

    def save_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def claim_ingestion_job(self, job_id: UUID) -> IngestionJob | None:
        """Atomically move a pending job to running. Returns None if already claimed."""
        started_at = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            self._db.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == job_id,
                    IngestionJob.status == IngestionJobStatus.PENDING,
                )
                .values(
                    status=IngestionJobStatus.RUNNING,
                    started_at=started_at,
                    error_message=None,
                )
            ),
        )
        self._db.commit()
        if result.rowcount == 0:
            return None
        return self.get_ingestion_job(job_id)

    def has_active_ingestion_job(self, document_id: UUID) -> bool:
        """True when a pending or running job already exists for the document."""
        count = self._db.scalar(
            select(func.count())
            .select_from(IngestionJob)
            .where(
                IngestionJob.document_id == document_id,
                IngestionJob.status.in_((IngestionJobStatus.PENDING, IngestionJobStatus.RUNNING)),
            )
        )
        return bool(count)

    def list_ingestion_jobs_for_document(self, document_id: UUID) -> list[IngestionJob]:
        statement = (
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(
                IngestionJob.attempt_number.desc(),
                IngestionJob.created_at.desc(),
            )
        )
        return list(self._db.scalars(statement).all())

    def fail_stale_ingestion_jobs(self, *, older_than: datetime) -> list[IngestionJob]:
        """Mark long-running/pending jobs failed and sync their documents."""
        stale = list(
            self._db.scalars(
                select(IngestionJob).where(
                    IngestionJob.status.in_(
                        (IngestionJobStatus.PENDING, IngestionJobStatus.RUNNING)
                    ),
                    or_(
                        and_(
                            IngestionJob.started_at.is_not(None),
                            IngestionJob.started_at < older_than,
                        ),
                        and_(
                            IngestionJob.started_at.is_(None),
                            IngestionJob.created_at < older_than,
                        ),
                    ),
                )
            ).all()
        )
        now = datetime.now(UTC)
        message = (
            "Ingestion job marked failed: exceeded stale timeout "
            "(process may have crashed or been restarted)"
        )
        for job in stale:
            job.status = IngestionJobStatus.FAILED
            job.error_message = message
            job.completed_at = now
            if job.started_at is not None:
                started = job.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                completed = now if now.tzinfo else now.replace(tzinfo=UTC)
                job.duration_ms = int((completed - started).total_seconds() * 1000)
            document = self.get_by_id(job.document_id)
            if document is not None and document.processing_status in {
                ProcessingStatus.PENDING,
                ProcessingStatus.PROCESSING,
            }:
                document.processing_status = ProcessingStatus.FAILED
                document.ingestion_stage = IngestionStage.FAILED
                document.processing_error = message
                self._db.add(document)
            self._db.add(job)
        if stale:
            self._db.commit()
            for job in stale:
                self._db.refresh(job)
        return stale

    def list_documents(
        self,
        *,
        page: int,
        page_size: int,
        department: str | None = None,
        category: str | None = None,
        status: ProcessingStatus | None = None,
        title_query: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Document], int]:
        filters = []
        if department:
            filters.append(Document.department == department)
        if category:
            filters.append(Document.category == category)
        if status:
            filters.append(Document.processing_status == status)

        sort_columns = {
            "created_at": Document.created_at,
            "updated_at": Document.updated_at,
            "title": Document.title,
            "department": Document.department,
            "category": Document.category,
            "processing_status": Document.processing_status,
        }
        sort_column = sort_columns.get(sort_by, Document.created_at)
        order = sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc()

        query = title_query.strip() if title_query else None
        if query:
            pattern = f"%{query}%"
            filters.append(
                or_(
                    Document.title.ilike(pattern),
                    Document.department.ilike(pattern),
                    Document.category.ilike(pattern),
                    DocumentChunk.content.ilike(pattern),
                )
            )
            base = (
                select(Document)
                .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
                .where(*filters)
                .distinct()
            )
        else:
            base = select(Document).where(*filters) if filters else select(Document)

        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = list(
            self._db.scalars(
                base.options(selectinload(Document.versions), selectinload(Document.uploaded_by))
                .order_by(order)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return items, total

    def add_document(self, document: Document) -> Document:
        self._db.add(document)
        self._db.commit()
        self._db.refresh(document)
        return document

    def save(self, document: Document) -> Document:
        self._db.add(document)
        self._db.commit()
        self._db.refresh(document)
        return document

    def delete(self, document: Document) -> None:
        self._db.delete(document)
        self._db.commit()

    def create_ingestion_job(
        self,
        *,
        document_id: UUID,
        document_version_id: UUID,
        attempt_number: int,
    ) -> IngestionJob:
        job = IngestionJob(
            document_id=document_id,
            document_version_id=document_version_id,
            status=IngestionJobStatus.PENDING,
            attempt_number=attempt_number,
        )
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def latest_ingestion_job(self, document_id: UUID) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(
                IngestionJob.attempt_number.desc(),
                IngestionJob.created_at.desc(),
            )
            .limit(1)
        )
        return self._db.scalar(statement)

    def next_attempt_number(self, document_id: UUID) -> int:
        current = self._db.scalar(
            select(func.max(IngestionJob.attempt_number)).where(
                IngestionJob.document_id == document_id
            )
        )
        return int(current or 0) + 1

    def get_current_version(self, document: Document) -> DocumentVersion | None:
        return self._db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_number == document.current_version,
            )
        )
