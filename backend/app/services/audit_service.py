"""Audit logging helpers."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.request_context import get_request_id
from app.models.audit import AuditLog

logger = get_logger(__name__)


class AuditService:
    """Persist security-relevant actions without breaking the primary request."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        *,
        action: str,
        actor_user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | UUID | None = None,
        success: bool = True,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        try:
            entry = AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                success=success,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:400] or None,
                details=json.dumps(details) if details else None,
                error_message=(error_message or "")[:2000] or None,
                request_id=get_request_id(),
            )
            self._db.add(entry)
            self._db.commit()
        except Exception:
            self._db.rollback()
            logger.exception("Failed to write audit log for action=%s", action)
