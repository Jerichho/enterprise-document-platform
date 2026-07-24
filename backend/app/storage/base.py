"""Storage service protocol."""

from __future__ import annotations

from typing import Protocol


class StorageService(Protocol):
    """Abstraction over object storage backends (local disk, Azure Blob, …)."""

    def save(self, *, key: str, data: bytes, content_type: str) -> str:
        """Persist bytes at key and return the stored key."""

    def read(self, key: str) -> bytes:
        """Read object bytes by key."""

    def delete(self, key: str) -> None:
        """Delete an object if it exists (idempotent)."""

    def exists(self, key: str) -> bool:
        """Return True when the object exists."""
