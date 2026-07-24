"""Admin analytics computed from stored application data."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.chunk import DocumentChunk
from app.models.conversation import Citation, Conversation, Message
from app.models.document import Document, IngestionJob
from app.models.enums import IngestionJobStatus, MessageRole, ProcessingStatus
from app.models.user import User


class StatusCount(BaseModel):
    status: str
    count: int


class NamedCount(BaseModel):
    name: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class TimeBucketCount(BaseModel):
    date: date
    count: int


class RecentUpload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    department: str
    category: str
    processing_status: ProcessingStatus
    created_at: datetime


class FailedIngestionJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    attempt_number: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class CitedDocument(BaseModel):
    document_id: UUID | None
    document_title: str
    citation_count: int


class RecentError(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    error_message: str | None
    created_at: datetime


class AnalyticsResponse(BaseModel):
    # Lifetime inventory
    total_users: int
    total_documents: int
    total_indexed_chunks: int
    total_conversations: int
    total_questions: int
    completed_ingestion_jobs: int
    failed_ingestion_jobs_count: int

    # Latency (from measured timings; null when no samples)
    average_e2e_latency_ms: float | None
    average_embedding_latency_ms: float | None
    average_vector_search_latency_ms: float | None
    average_llm_latency_ms: float | None
    # Backward-compatible alias for prior clients
    average_response_latency_ms: float | None

    documents_by_status: list[StatusCount]
    documents_by_department: list[NamedCount]
    documents_by_category: list[CategoryCount]
    questions_over_time: list[TimeBucketCount]
    most_cited_documents: list[CitedDocument]
    recent_uploads: list[RecentUpload]
    failed_ingestion_jobs: list[FailedIngestionJob]
    recent_system_errors: list[RecentError]
    most_used_categories: list[CategoryCount] = Field(default_factory=list)

    range_start: datetime | None = None
    range_end: datetime | None = None


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    document_version_id: UUID
    status: IngestionJobStatus
    attempt_number: int
    error_message: str | None
    embedding_latency_ms: int | None = None
    duration_ms: int | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IngestionJobListResponse(BaseModel):
    items: list[IngestionJobResponse]
    total: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    success: bool
    ip_address: str | None
    details: str | None
    error_message: str | None
    request_id: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AnalyticsService:
    """Aggregate operational metrics from the relational store."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_analytics(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> AnalyticsResponse:
        range_start, range_end = self._normalize_range(start, end)

        total_users = self._count(User)
        total_documents = self._count(Document)
        total_indexed_chunks = self._count(DocumentChunk)
        total_conversations = self._count(Conversation)

        question_filters = [Message.role == MessageRole.USER]
        question_filters.extend(self._created_between(Message.created_at, range_start, range_end))
        total_questions = (
            self._db.scalar(select(func.count()).select_from(Message).where(*question_filters)) or 0
        )

        completed_jobs = (
            self._db.scalar(
                select(func.count())
                .select_from(IngestionJob)
                .where(
                    IngestionJob.status == IngestionJobStatus.COMPLETED,
                    *self._created_between(IngestionJob.created_at, range_start, range_end),
                )
            )
            or 0
        )
        failed_jobs_count = (
            self._db.scalar(
                select(func.count())
                .select_from(IngestionJob)
                .where(
                    IngestionJob.status == IngestionJobStatus.FAILED,
                    *self._created_between(IngestionJob.created_at, range_start, range_end),
                )
            )
            or 0
        )

        avg_llm = self._avg_message_latency(Message.llm_latency_ms, range_start, range_end)
        avg_embed_query = self._avg_message_latency(
            Message.embedding_latency_ms, range_start, range_end
        )
        avg_vector = self._avg_message_latency(
            Message.vector_search_latency_ms, range_start, range_end
        )
        avg_ingest_embed = self._avg_ingestion_embedding(range_start, range_end)
        # Prefer query-embedding latency; fall back to ingestion embedding samples.
        avg_embedding = avg_embed_query if avg_embed_query is not None else avg_ingest_embed
        avg_e2e = self._avg_e2e_latency(range_start, range_end)

        status_rows = self._db.execute(
            select(Document.processing_status, func.count()).group_by(Document.processing_status)
        ).all()
        documents_by_status = [
            StatusCount(status=str(status), count=int(count)) for status, count in status_rows
        ]

        dept_filters = self._created_between(Document.created_at, range_start, range_end)
        dept_rows = self._db.execute(
            select(Document.department, func.count())
            .where(*dept_filters)
            .group_by(Document.department)
            .order_by(desc(func.count()))
            .limit(10)
        ).all()
        documents_by_department = [
            NamedCount(name=str(name), count=int(count)) for name, count in dept_rows
        ]

        category_rows = self._db.execute(
            select(Document.category, func.count())
            .where(*dept_filters)
            .group_by(Document.category)
            .order_by(desc(func.count()))
            .limit(10)
        ).all()
        documents_by_category = [
            CategoryCount(category=str(name), count=int(count)) for name, count in category_rows
        ]

        day_expr = func.date(Message.created_at)
        question_day_rows = self._db.execute(
            select(day_expr, func.count())
            .where(*question_filters)
            .group_by(day_expr)
            .order_by(day_expr.asc())
        ).all()
        questions_over_time = [
            TimeBucketCount(date=self._as_date(bucket), count=int(count))
            for bucket, count in question_day_rows
        ]

        citation_filters = self._created_between(Message.created_at, range_start, range_end)
        cited_rows = self._db.execute(
            select(Citation.document_id, Citation.document_title, func.count())
            .join(Message, Message.id == Citation.message_id)
            .where(*citation_filters)
            .group_by(Citation.document_id, Citation.document_title)
            .order_by(desc(func.count()))
            .limit(10)
        ).all()
        most_cited_documents = [
            CitedDocument(
                document_id=document_id,
                document_title=title,
                citation_count=int(count),
            )
            for document_id, title, count in cited_rows
        ]

        upload_filters = self._created_between(Document.created_at, range_start, range_end)
        recent_uploads = list(
            self._db.scalars(
                select(Document)
                .where(*upload_filters)
                .order_by(desc(Document.created_at))
                .limit(10)
            ).all()
        )

        failed_job_filters = [
            IngestionJob.status == IngestionJobStatus.FAILED,
            *self._created_between(IngestionJob.created_at, range_start, range_end),
        ]
        failed_jobs = list(
            self._db.scalars(
                select(IngestionJob)
                .where(*failed_job_filters)
                .order_by(desc(IngestionJob.created_at))
                .limit(20)
            ).all()
        )

        error_filters = [
            AuditLog.success.is_(False),
            *self._created_between(AuditLog.created_at, range_start, range_end),
        ]
        recent_errors = list(
            self._db.scalars(
                select(AuditLog).where(*error_filters).order_by(desc(AuditLog.created_at)).limit(20)
            ).all()
        )

        return AnalyticsResponse(
            total_users=int(total_users),
            total_documents=int(total_documents),
            total_indexed_chunks=int(total_indexed_chunks),
            total_conversations=int(total_conversations),
            total_questions=int(total_questions),
            completed_ingestion_jobs=int(completed_jobs),
            failed_ingestion_jobs_count=int(failed_jobs_count),
            average_e2e_latency_ms=avg_e2e,
            average_embedding_latency_ms=avg_embedding,
            average_vector_search_latency_ms=avg_vector,
            average_llm_latency_ms=avg_llm,
            average_response_latency_ms=avg_llm,
            documents_by_status=documents_by_status,
            documents_by_department=documents_by_department,
            documents_by_category=documents_by_category,
            questions_over_time=questions_over_time,
            most_cited_documents=most_cited_documents,
            recent_uploads=[RecentUpload.model_validate(item) for item in recent_uploads],
            failed_ingestion_jobs=[FailedIngestionJob.model_validate(job) for job in failed_jobs],
            recent_system_errors=[RecentError.model_validate(item) for item in recent_errors],
            most_used_categories=documents_by_category,
            range_start=range_start,
            range_end=range_end,
        )

    def list_ingestion_jobs(
        self,
        *,
        status_filter: IngestionJobStatus | None = None,
        limit: int = 50,
    ) -> IngestionJobListResponse:
        filters = []
        if status_filter is not None:
            filters.append(IngestionJob.status == status_filter)

        count_statement = select(func.count()).select_from(IngestionJob)
        statement = select(IngestionJob)
        if filters:
            count_statement = count_statement.where(*filters)
            statement = statement.where(*filters)

        total = self._db.scalar(count_statement) or 0
        items = list(
            self._db.scalars(statement.order_by(desc(IngestionJob.created_at)).limit(limit)).all()
        )
        return IngestionJobListResponse(
            items=[IngestionJobResponse.model_validate(item) for item in items],
            total=int(total),
        )

    def list_audit_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        action: str | None = None,
        success: bool | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> AuditLogListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        range_start, range_end = self._normalize_range(start, end)
        filters = [*self._created_between(AuditLog.created_at, range_start, range_end)]
        if action:
            filters.append(AuditLog.action == action)
        if success is not None:
            filters.append(AuditLog.success.is_(success))

        base = select(AuditLog).where(*filters) if filters else select(AuditLog)
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        items = list(
            self._db.scalars(
                base.order_by(desc(AuditLog.created_at))
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(item) for item in items],
            total=int(total),
            page=page,
            page_size=page_size,
        )

    def _count(self, model: type[object]) -> int:
        return int(self._db.scalar(select(func.count()).select_from(model)) or 0)

    def _normalize_range(
        self,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        range_end = end or now
        range_start = start or (range_end - timedelta(days=30))
        if range_start.tzinfo is None:
            range_start = range_start.replace(tzinfo=UTC)
        if range_end.tzinfo is None:
            range_end = range_end.replace(tzinfo=UTC)
        if range_start > range_end:
            range_start, range_end = range_end, range_start
        return range_start, range_end

    def _created_between(
        self,
        column: Any,
        start: datetime,
        end: datetime,
    ) -> list[Any]:
        return [column >= start, column <= end]

    def _as_date(self, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    def _avg_message_latency(
        self,
        column: Any,
        start: datetime,
        end: datetime,
    ) -> float | None:
        value = self._db.scalar(
            select(func.avg(column)).where(
                Message.role == MessageRole.ASSISTANT,
                column.is_not(None),
                *self._created_between(Message.created_at, start, end),
            )
        )
        return round(float(value), 2) if value is not None else None

    def _avg_ingestion_embedding(self, start: datetime, end: datetime) -> float | None:
        value = self._db.scalar(
            select(func.avg(IngestionJob.embedding_latency_ms)).where(
                IngestionJob.embedding_latency_ms.is_not(None),
                *self._created_between(IngestionJob.created_at, start, end),
            )
        )
        return round(float(value), 2) if value is not None else None

    def _avg_e2e_latency(self, start: datetime, end: datetime) -> float | None:
        e2e = (
            func.coalesce(Message.embedding_latency_ms, 0)
            + func.coalesce(Message.vector_search_latency_ms, 0)
            + func.coalesce(Message.llm_latency_ms, 0)
        )
        has_sample = case(
            (
                (Message.embedding_latency_ms.is_not(None))
                | (Message.vector_search_latency_ms.is_not(None))
                | (Message.llm_latency_ms.is_not(None)),
                1,
            ),
            else_=None,
        )
        value = self._db.scalar(
            select(func.avg(e2e)).where(
                Message.role == MessageRole.ASSISTANT,
                has_sample.is_not(None),
                *self._created_between(Message.created_at, start, end),
            )
        )
        return round(float(value), 2) if value is not None else None
