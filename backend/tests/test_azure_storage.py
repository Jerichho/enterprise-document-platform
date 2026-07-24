"""Azure Blob storage unit tests (mocked SDK — no live cloud calls)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.storage.azure import AzureBlobStorageService
from app.storage.factory import build_storage_service


def test_azure_storage_requires_connection_string() -> None:
    with pytest.raises(AppError) as exc:
        AzureBlobStorageService(connection_string="", container="documents")
    assert exc.value.code == "missing_azure_storage_config"


def test_azure_storage_roundtrip_with_mocked_sdk() -> None:
    container = MagicMock()
    blob = MagicMock()
    blob.download_blob.return_value.readall.return_value = b"hello"
    blob.get_blob_properties.return_value = SimpleNamespace()
    container.get_blob_client.return_value = blob
    container.create_container.return_value = None
    container.get_container_properties.return_value = SimpleNamespace()

    client = MagicMock()
    client.get_container_client.return_value = container

    with patch("azure.storage.blob.BlobServiceClient") as factory:
        factory.from_connection_string.return_value = client
        with patch("azure.storage.blob.ContentSettings"):
            service = AzureBlobStorageService(
                connection_string="UseDevelopmentStorage=true",
                container="documents",
            )
            assert service.save(key="documents/a.txt", data=b"hello", content_type="text/plain")
            assert service.read("documents/a.txt") == b"hello"
            assert service.exists("documents/a.txt") is True
            service.delete("documents/a.txt")
            ok, detail = service.ping()
            assert ok is True
            assert "documents" in detail


def test_azure_storage_rejects_path_traversal() -> None:
    container = MagicMock()
    container.create_container.return_value = None
    client = MagicMock()
    client.get_container_client.return_value = container
    with patch("azure.storage.blob.BlobServiceClient") as factory:
        factory.from_connection_string.return_value = client
        service = AzureBlobStorageService(
            connection_string="UseDevelopmentStorage=true",
            container="documents",
        )
        with pytest.raises(AppError) as exc:
            service.save(key="../etc/passwd", data=b"x", content_type="text/plain")
        assert exc.value.code == "invalid_storage_key"


def test_build_storage_service_azure_uses_settings() -> None:
    settings = Settings(
        secret_key="test-secret-key-at-least-16-chars",
        storage_backend="azure",
        azure_storage_connection_string="UseDevelopmentStorage=true",
        azure_storage_container="docs",
    )
    container = MagicMock()
    container.create_container.return_value = None
    client = MagicMock()
    client.get_container_client.return_value = container
    with patch("azure.storage.blob.BlobServiceClient") as factory:
        factory.from_connection_string.return_value = client
        service = build_storage_service(settings)
        assert isinstance(service, AzureBlobStorageService)
