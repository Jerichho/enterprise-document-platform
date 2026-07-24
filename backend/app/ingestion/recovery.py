"""Helpers for recovering orphaned ingestion jobs after process restarts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.database.session import SessionLocal
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)


def recover_stale_ingestion_jobs(settings: Settings | None = None) -> int:
    """Fail jobs stuck in pending/running longer than the configured timeout.

    FastAPI BackgroundTasks run in-process. A crash or deploy can leave jobs
    orphaned; this sweep makes them reprocessable again.
    """
    cfg = settings or get_settings()
    if cfg.app_env == "test":
        return 0

    cutoff = datetime.now(UTC) - timedelta(minutes=cfg.ingestion_stale_job_minutes)
    db = SessionLocal()
    try:
        stale = DocumentRepository(db).fail_stale_ingestion_jobs(older_than=cutoff)
        if stale:
            logger.warning(
                "Recovered %s stale ingestion job(s) older than %s minutes",
                len(stale),
                cfg.ingestion_stale_job_minutes,
            )
        return len(stale)
    finally:
        db.close()
