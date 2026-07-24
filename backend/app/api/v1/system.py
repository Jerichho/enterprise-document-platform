"""System health and readiness endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.database import check_database_connection, check_pgvector_extension
from app.schemas.health import DependencyStatus, HealthResponse, ReadyResponse

router = APIRouter(tags=["system"])


def _llm_provider_status() -> DependencyStatus:
    settings = get_settings()
    if settings.llm_provider == "fake" or settings.app_env == "test":
        return DependencyStatus(
            name="llm_provider",
            status="ok",
            detail=f"Using {settings.llm_provider} provider",
        )
    if settings.llm_provider == "together":
        if not settings.together_api_key:
            return DependencyStatus(
                name="llm_provider",
                status="degraded",
                detail="TOGETHER_API_KEY is not configured",
            )
        return DependencyStatus(
            name="llm_provider",
            status="ok",
            detail=f"Together.ai configured ({settings.together_model})",
        )
    return DependencyStatus(
        name="llm_provider",
        status="unavailable",
        detail=f"Unsupported LLM provider '{settings.llm_provider}'",
    )


def _embedding_provider_status() -> DependencyStatus:
    settings = get_settings()
    if settings.embedding_provider == "fake" or settings.app_env == "test":
        return DependencyStatus(
            name="embedding_provider",
            status="ok",
            detail=f"Using {settings.embedding_provider} provider",
        )
    if settings.embedding_provider == "together":
        if not settings.together_api_key:
            return DependencyStatus(
                name="embedding_provider",
                status="degraded",
                detail="TOGETHER_API_KEY is not configured",
            )
        return DependencyStatus(
            name="embedding_provider",
            status="ok",
            detail=f"Together embeddings configured ({settings.embedding_model})",
        )
    return DependencyStatus(
        name="embedding_provider",
        status="unavailable",
        detail=f"Embedding provider '{settings.embedding_provider}' is not ready",
    )


def _storage_status() -> DependencyStatus:
    settings = get_settings()
    if settings.storage_backend == "local":
        root = Path(settings.storage_local_path)
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe = root / ".ekp_healthcheck"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return DependencyStatus(
                name="storage",
                status="ok",
                detail=f"Local storage writable ({root})",
            )
        except OSError:
            return DependencyStatus(
                name="storage",
                status="unavailable",
                detail="Local storage path is not writable",
            )
    if settings.storage_backend == "azure":
        if not settings.azure_storage_connection_string.strip():
            return DependencyStatus(
                name="storage",
                status="unavailable",
                detail="AZURE_STORAGE_CONNECTION_STRING is not configured",
            )
        try:
            from app.storage.azure import AzureBlobStorageService

            service = AzureBlobStorageService(
                connection_string=settings.azure_storage_connection_string,
                container=settings.azure_storage_container,
            )
            ok, detail = service.ping()
            return DependencyStatus(
                name="storage",
                status="ok" if ok else "unavailable",
                detail=detail,
            )
        except AppError as exc:
            return DependencyStatus(
                name="storage",
                status="unavailable",
                detail=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            return DependencyStatus(
                name="storage",
                status="unavailable",
                detail=f"Azure Blob probe failed: {exc.__class__.__name__}",
            )
    return DependencyStatus(
        name="storage",
        status="unavailable",
        detail=f"Unsupported storage backend '{settings.storage_backend}'",
    )


def _pgvector_status() -> DependencyStatus:
    ok, detail = check_pgvector_extension()
    return DependencyStatus(
        name="pgvector",
        status="ok" if ok else "unavailable",
        detail=detail,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — process is running."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
def ready() -> JSONResponse:
    """Readiness probe — required dependencies are configured and reachable.

    Required checks (database, pgvector, storage) failing → ``not_ready`` (503).
    Optional provider checks failing → ``degraded`` (200) so the API can still
    serve non-RAG routes while AI features are unavailable.
    """
    settings = get_settings()
    db_ok = check_database_connection()
    checks = [
        DependencyStatus(
            name="database",
            status="ok" if db_ok else "unavailable",
            detail=None if db_ok else "Unable to connect to PostgreSQL",
        ),
        _pgvector_status(),
        _storage_status(),
        _llm_provider_status(),
        _embedding_provider_status(),
    ]

    required = {"database", "pgvector", "storage"}
    required_failed = any(
        check.name in required and check.status == "unavailable" for check in checks
    )

    if required_failed:
        overall: Literal["ready", "degraded", "not_ready"] = "not_ready"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(check.status != "ok" for check in checks):
        overall = "degraded"
        http_status = status.HTTP_200_OK
    else:
        overall = "ready"
        http_status = status.HTTP_200_OK

    demo_mode = settings.app_env != "production" and (
        settings.llm_provider == "fake" or settings.embedding_provider == "fake"
    )
    payload = ReadyResponse(
        status=overall,
        environment=settings.app_env,
        version=__version__,
        checks=checks,
        demo_mode=demo_mode,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
    )
    return JSONResponse(
        status_code=http_status,
        content=payload.model_dump(),
    )
