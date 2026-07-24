"""Upload file validation helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.enums import DocumentFileType

_ALLOWED_EXTENSIONS: dict[str, DocumentFileType] = {
    ".pdf": DocumentFileType.PDF,
    ".docx": DocumentFileType.DOCX,
    ".txt": DocumentFileType.TXT,
}

_ALLOWED_CONTENT_TYPES: dict[DocumentFileType, set[str]] = {
    DocumentFileType.PDF: {"application/pdf", "application/x-pdf"},
    DocumentFileType.DOCX: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
    DocumentFileType.TXT: {
        "text/plain",
        "text/plain; charset=utf-8",
        "application/octet-stream",
    },
}

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._\- ]+")


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """Result of validating an uploaded file."""

    original_filename: str
    safe_filename: str
    file_type: DocumentFileType
    content_type: str
    size_bytes: int
    checksum_sha256: str
    data: bytes


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe basename."""
    name = filename.replace("\\", "/").split("/")[-1].strip()
    name = _UNSAFE_FILENAME.sub("_", name)
    name = name.strip("._ ") or "upload"
    return name[:200]


def validate_upload(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    settings: Settings,
) -> ValidatedUpload:
    """Validate extension, size, content type, and basic magic bytes."""
    if not filename:
        raise AppError("Filename is required", status_code=400, code="invalid_file")

    lower_name = filename.lower()
    extension = next((ext for ext in _ALLOWED_EXTENSIONS if lower_name.endswith(ext)), None)
    if extension is None:
        raise AppError(
            "Unsupported file type. Allowed: PDF, DOCX, TXT",
            status_code=400,
            code="unsupported_file_type",
        )

    file_type = _ALLOWED_EXTENSIONS[extension]
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if len(data) == 0:
        raise AppError("Uploaded file is empty", status_code=400, code="empty_file")
    if len(data) > max_bytes:
        raise AppError(
            f"File exceeds maximum size of {settings.upload_max_size_mb} MB",
            status_code=400,
            code="file_too_large",
        )

    raw_content_type = content_type or "application/octet-stream"
    normalized_content_type = raw_content_type.split(";")[0].strip().lower()
    allowed_types = _ALLOWED_CONTENT_TYPES[file_type]
    # Allow generic octet-stream; still enforce magic-byte checks below.
    if (
        normalized_content_type not in allowed_types
        and normalized_content_type != "application/octet-stream"
    ):
        raise AppError(
            f"Content type '{content_type}' does not match file extension",
            status_code=400,
            code="content_type_mismatch",
        )

    _validate_magic_bytes(file_type, data)

    checksum = hashlib.sha256(data).hexdigest()
    safe_name = sanitize_filename(filename)
    return ValidatedUpload(
        original_filename=filename.split("/")[-1].split("\\")[-1],
        safe_filename=safe_name,
        file_type=file_type,
        content_type=normalized_content_type or "application/octet-stream",
        size_bytes=len(data),
        checksum_sha256=checksum,
        data=data,
    )


def _validate_magic_bytes(file_type: DocumentFileType, data: bytes) -> None:
    if file_type == DocumentFileType.PDF and not data.startswith(b"%PDF"):
        raise AppError("File content is not a valid PDF", status_code=400, code="invalid_pdf")
    if file_type == DocumentFileType.DOCX and not data.startswith(b"PK"):
        # DOCX is a ZIP package.
        raise AppError("File content is not a valid DOCX", status_code=400, code="invalid_docx")
    if file_type == DocumentFileType.TXT:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(
                "TXT files must be valid UTF-8 text",
                status_code=400,
                code="invalid_txt",
            ) from exc
