"""Together.ai embedding provider."""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.provider_http import post_json_with_retries


class TogetherEmbeddingProvider:
    """Generate embeddings through the Together.ai HTTP API."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not settings.together_api_key:
            raise AppError(
                "TOGETHER_API_KEY is required for the Together embedding provider",
                status_code=500,
                code="missing_together_api_key",
            )
        self._settings = settings
        self._dimensions = settings.embedding_dimensions
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batch_size = max(1, self._settings.embedding_batch_size)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text])[0]

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = f"{self._settings.together_base_url.rstrip('/')}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._settings.together_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self._settings.embedding_model, "input": texts}
        response = post_json_with_retries(
            url,
            headers=headers,
            payload=payload,
            timeout=float(self._settings.llm_request_timeout_seconds),
            max_retries=self._settings.llm_max_retries,
            error_code="embedding_provider_error",
            error_message="Failed to generate embeddings from Together.ai",
            client=self._client,
        )
        body = response.json()
        data = body.get("data") or []
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        vectors = [list(map(float, item["embedding"])) for item in ordered]
        if len(vectors) != len(texts):
            raise AppError(
                "Embedding provider returned an unexpected result count",
                status_code=502,
                code="embedding_count_mismatch",
            )
        return vectors
