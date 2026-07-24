"""Overlapping text chunking with page metadata preservation."""

from __future__ import annotations

from dataclasses import dataclass

from app.ingestion.cleaning import clean_segments
from app.ingestion.extraction import TextSegment


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk ready for embedding and persistence."""

    index: int
    content: str
    page_number: int | None
    char_count: int


def chunk_segments(
    segments: list[TextSegment],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Split cleaned segments into overlapping character windows."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    cleaned = clean_segments(segments)
    if not cleaned:
        return []

    # Build a linear stream of characters tagged with page numbers.
    stream: list[tuple[str, int | None]] = []
    for segment in cleaned:
        if stream and not stream[-1][0].endswith("\n"):
            stream.append(("\n\n", segment.page_number))
        for char in segment.text:
            stream.append((char, segment.page_number))

    total = len(stream)
    if total == 0:
        return []

    step = chunk_size - chunk_overlap
    chunks: list[TextChunk] = []
    start = 0
    index = 0
    while start < total:
        end = min(start + chunk_size, total)
        window = stream[start:end]
        content = "".join(char for char, _ in window).strip()
        if content:
            page_number = _dominant_page(window)
            chunks.append(
                TextChunk(
                    index=index,
                    content=content,
                    page_number=page_number,
                    char_count=len(content),
                )
            )
            index += 1
        if end >= total:
            break
        start += step
    return chunks


def _dominant_page(window: list[tuple[str, int | None]]) -> int | None:
    counts: dict[int, int] = {}
    for _, page in window:
        if page is None:
            continue
        counts[page] = counts.get(page, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]
