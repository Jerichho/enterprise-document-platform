"""Text normalization helpers for ingestion."""

from __future__ import annotations

import re
import unicodedata

from app.ingestion.extraction import TextSegment

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


def clean_text(text: str) -> str:
    """Normalize whitespace and Unicode for downstream chunking."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _MULTI_SPACE.sub(" ", normalized)
    normalized = _MULTI_NEWLINE.sub("\n\n", normalized)
    return normalized.strip()


def clean_segments(segments: list[TextSegment]) -> list[TextSegment]:
    """Clean each segment and drop empty results."""
    cleaned: list[TextSegment] = []
    for segment in segments:
        text = clean_text(segment.text)
        if text:
            cleaned.append(TextSegment(text=text, page_number=segment.page_number))
    return cleaned
