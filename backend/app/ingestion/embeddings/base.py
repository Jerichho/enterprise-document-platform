"""Embedding provider abstractions."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Interface for text embedding backends."""

    @property
    def dimensions(self) -> int:
        """Expected embedding dimensionality."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more document passages."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
