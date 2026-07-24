"""Retrieved chunk with similarity score."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.chunk import DocumentChunk


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """A document chunk scored for relevance to a query."""

    chunk: DocumentChunk
    score: float
    document_title: str
    department: str
    category: str


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(dot / (left_norm * right_norm))
