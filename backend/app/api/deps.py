"""Helpers for writing audit events from API routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.services.audit_service import AuditService


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def write_audit(
    db: Session,
    request: Request,
    *,
    action: str,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | UUID | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    AuditService(db).record(
        action=action,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        success=success,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        details=details,
        error_message=error_message,
    )
