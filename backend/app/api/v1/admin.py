"""Admin API routes for analytics, jobs, and audit logs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models.enums import IngestionJobStatus
from app.repositories.document_repository import DocumentRepository
from app.security.dependencies import RequireAdmin
from app.services.analytics_service import (
    AnalyticsResponse,
    AnalyticsService,
    AuditLogListResponse,
    IngestionJobListResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class StaleJobRecoveryResponse(BaseModel):
    recovered: int
    job_ids: list[UUID] = Field(default_factory=list)
    stale_after_minutes: int


def get_analytics_service(db: Annotated[Session, Depends(get_db)]) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("/access-check")
def access_check(current_user: RequireAdmin) -> dict[str, str]:
    """Verify the caller has the admin role."""
    return {"status": "ok", "role": current_user.role.value}


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    _admin: RequireAdmin,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    start: Annotated[datetime | None, Query(description="Range start (ISO 8601)")] = None,
    end: Annotated[datetime | None, Query(description="Range end (ISO 8601)")] = None,
) -> AnalyticsResponse:
    """Operational analytics computed from stored application data."""
    return service.get_analytics(start=start, end=end)


@router.get("/ingestion-jobs", response_model=IngestionJobListResponse)
def ingestion_jobs(
    _admin: RequireAdmin,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    status_filter: Annotated[IngestionJobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> IngestionJobListResponse:
    """List recent ingestion jobs, optionally filtered by status."""
    return service.list_ingestion_jobs(status_filter=status_filter, limit=limit)


@router.post("/ingestion-jobs/recover-stale", response_model=StaleJobRecoveryResponse)
def recover_stale_ingestion_jobs(
    _admin: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StaleJobRecoveryResponse:
    """Mark orphaned pending/running jobs as failed so documents can be reprocessed."""
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.ingestion_stale_job_minutes)
    recovered = DocumentRepository(db).fail_stale_ingestion_jobs(older_than=cutoff)
    return StaleJobRecoveryResponse(
        recovered=len(recovered),
        job_ids=[job.id for job in recovered],
        stale_after_minutes=settings.ingestion_stale_job_minutes,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def audit_logs(
    _admin: RequireAdmin,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    action: str | None = None,
    success: bool | None = None,
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> AuditLogListResponse:
    """List audit log entries for security and operations review."""
    return service.list_audit_logs(
        page=page,
        page_size=page_size,
        action=action,
        success=success,
        start=start,
        end=end,
    )
