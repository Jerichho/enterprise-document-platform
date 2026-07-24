"""Storage backend factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.storage.azure import AzureBlobStorageService
from app.storage.base import StorageService
from app.storage.local import LocalStorageService


def build_storage_service(settings: Settings) -> StorageService:
    """Create the configured storage backend instance."""
    if settings.storage_backend == "local":
        return LocalStorageService(settings.storage_local_path)
    if settings.storage_backend == "azure":
        return AzureBlobStorageService(
            connection_string=settings.azure_storage_connection_string,
            container=settings.azure_storage_container,
        )
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")


@lru_cache
def get_storage_service() -> StorageService:
    """Cached storage service for FastAPI dependency injection."""
    return build_storage_service(get_settings())
