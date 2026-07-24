"""Text extraction from uploaded document bytes."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.enums import DocumentFileType

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TextSegment:
    """A contiguous text region, optionally tied to a page number."""

    text: str
    page_number: int | None


def extract_text(data: bytes, file_type: DocumentFileType) -> list[TextSegment]:
    """Extract text segments from a supported document type."""
    if file_type == DocumentFileType.TXT:
        return _extract_txt(data)
    if file_type == DocumentFileType.PDF:
        return _extract_pdf(data)
    if file_type == DocumentFileType.DOCX:
        return _extract_docx(data)
    raise AppError(
        f"Unsupported file type for extraction: {file_type}",
        status_code=400,
        code="unsupported_file_type",
    )


def _extract_txt(data: bytes) -> list[TextSegment]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(
            "TXT files must be valid UTF-8 text",
            status_code=400,
            code="invalid_txt",
        ) from exc
    return [TextSegment(text=text, page_number=1)]


def _extract_pdf(data: bytes) -> list[TextSegment]:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise AppError(
            "Unable to read PDF content",
            status_code=400,
            code="pdf_extract_failed",
        ) from exc

    segments: list[TextSegment] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("PDF page %s text extraction failed: %s", index, exc)
            text = ""
        segments.append(TextSegment(text=text, page_number=index))
    if not any(segment.text.strip() for segment in segments):
        raise AppError(
            "PDF contained no extractable text",
            status_code=422,
            code="empty_extraction",
        )
    return segments


def _extract_docx(data: bytes) -> list[TextSegment]:
    try:
        document = DocxDocument(BytesIO(data))
    except Exception as exc:
        raise AppError(
            "Unable to read DOCX content",
            status_code=400,
            code="docx_extract_failed",
        ) from exc

    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n".join(paragraphs)
    if not text.strip():
        raise AppError(
            "DOCX contained no extractable text",
            status_code=422,
            code="empty_extraction",
        )
    # python-docx does not expose reliable page breaks; treat as a single logical page.
    return [TextSegment(text=text, page_number=1)]
