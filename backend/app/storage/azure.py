"""Azure Blob Storage backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.exceptions import AppError


class AzureBlobStorageService:
    """Object storage backed by Azure Blob Storage.

    Requires the optional ``azure`` extra::

        pip install -e ".[azure]"

    and ``AZURE_STORAGE_CONNECTION_STRING`` (+ container name).
    """

    def __init__(self, *, connection_string: str, container: str) -> None:
        if not connection_string.strip():
            raise AppError(
                "AZURE_STORAGE_CONNECTION_STRING is required when STORAGE_BACKEND=azure",
                status_code=500,
                code="missing_azure_storage_config",
            )
        if not container.strip():
            raise AppError(
                "AZURE_STORAGE_CONTAINER is required when STORAGE_BACKEND=azure",
                status_code=500,
                code="missing_azure_storage_config",
            )
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise AppError(
                "Azure storage dependencies are not installed. Run: pip install -e '.[azure]'",
                status_code=500,
                code="azure_storage_dependency_missing",
            ) from exc

        self._container_name = container.strip()
        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container = self._client.get_container_client(self._container_name)
        try:
            self._container.create_container()
        except Exception as exc:  # noqa: BLE001 — SDK raises several conflict types
            # ContainerAlreadyExists is fine; anything else re-raised as AppError.
            message = str(exc).lower()
            if "containeralreadyexists" not in message and "already exists" not in message:
                raise AppError(
                    "Unable to access Azure Blob container",
                    status_code=502,
                    code="azure_storage_error",
                ) from exc

    def save(self, *, key: str, data: bytes, content_type: str) -> str:
        blob_key = self._normalize_key(key)
        blob = self._container.get_blob_client(blob_key)
        try:
            from azure.storage.blob import ContentSettings

            blob.upload_blob(
                data,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        except Exception as exc:  # noqa: BLE001 — Azure SDK surface is broad
            raise AppError(
                "Failed to upload object to Azure Blob Storage",
                status_code=502,
                code="azure_storage_error",
            ) from exc
        return blob_key

    def read(self, key: str) -> bytes:
        blob_key = self._normalize_key(key)
        blob = self._container.get_blob_client(blob_key)
        try:
            return blob.download_blob().readall()
        except Exception as exc:  # noqa: BLE001 — Azure SDK surface is broad
            raise AppError(
                "Stored file not found",
                status_code=404,
                code="storage_not_found",
            ) from exc

    def delete(self, key: str) -> None:
        blob_key = self._normalize_key(key)
        blob = self._container.get_blob_client(blob_key)
        try:
            blob.delete_blob()
        except Exception:  # noqa: BLE001 — idempotent delete
            return

    def exists(self, key: str) -> bool:
        blob_key = self._normalize_key(key)
        blob = self._container.get_blob_client(blob_key)
        try:
            blob.get_blob_properties()
            return True
        except Exception:  # noqa: BLE001 — missing blob => False
            return False

    def ping(self) -> tuple[bool, str]:
        """Lightweight connectivity probe for readiness checks."""
        try:
            self._container.get_container_properties()
            return True, f"Azure Blob container reachable ({self._container_name})"
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            return False, f"Azure Blob probe failed: {exc.__class__.__name__}"

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = key.replace("\\", "/").lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise AppError("Invalid storage key", status_code=400, code="invalid_storage_key")
        return normalized

    @property
    def raw_client(self) -> Any:
        """Expose the SDK client for tests."""
        return self._client
