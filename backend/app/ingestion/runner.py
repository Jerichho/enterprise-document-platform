"""Standalone ingestion job runner for background tasks."""

from __future__ import annotations

from uuid import UUID

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import SessionLocal
from app.ingestion.embeddings import get_embedding_provider
from app.ingestion.service import IngestionService
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.storage.factory import get_storage_service

logger = get_logger(__name__)


def process_ingestion_job(job_id: UUID) -> None:
    """Process an ingestion job using a fresh database session."""
    settings = get_settings()
    configure_logging(settings.log_level)
    db = SessionLocal()
    try:
        service = IngestionService(
            documents=DocumentRepository(db),
            chunks=ChunkRepository(db),
            storage=get_storage_service(),
            embeddings=get_embedding_provider(),
            settings=settings,
        )
        service.process_job(job_id)
    except Exception:
        logger.exception("Unhandled ingestion error for job %s", job_id)
    finally:
        db.close()
