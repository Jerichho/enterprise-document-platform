"""Embedding provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.ingestion.embeddings.base import EmbeddingProvider
from app.ingestion.embeddings.fake import FakeEmbeddingProvider
from app.ingestion.embeddings.together import TogetherEmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Create the configured embedding backend."""
    if settings.embedding_provider == "fake" or settings.app_env == "test":
        return FakeEmbeddingProvider(dimensions=settings.embedding_dimensions)
    if settings.embedding_provider == "together":
        return TogetherEmbeddingProvider(settings)
    raise AppError(
        f"Unknown embedding provider '{settings.embedding_provider}'",
        status_code=500,
        code="invalid_embedding_provider",
    )


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider(get_settings())
