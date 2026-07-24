"""Local filesystem storage backend."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import AppError


class LocalStorageService:
    """Store uploaded files under a configurable local directory."""

    def __init__(self, root_path: str | Path) -> None:
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, *, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise AppError("Stored file not found", status_code=404, code="storage_not_found")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def _resolve(self, key: str) -> Path:
        """Resolve a storage key and reject path traversal."""
        normalized = key.replace("\\", "/").lstrip("/")
        if ".." in Path(normalized).parts:
            raise AppError("Invalid storage key", status_code=400, code="invalid_storage_key")
        path = (self._root / normalized).resolve()
        if self._root not in path.parents and path != self._root:
            raise AppError("Invalid storage key", status_code=400, code="invalid_storage_key")
        return path
