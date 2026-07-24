"""Together.ai provider retry and failure handling tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.provider_http import post_json_with_retries
from app.ingestion.embeddings.together import TogetherEmbeddingProvider
from app.llm.base import LLMMessage
from app.llm.together import TogetherLLMProvider


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "secret_key": "test-secret-key-at-least-16-chars",
        "together_api_key": "test-key",
        "llm_max_retries": 2,
        "llm_request_timeout_seconds": 5,
        "embedding_dimensions": 4,
        "embedding_batch_size": 8,
        "embedding_model": "test-embed-model",
        "together_model": "test-chat-model",
        "together_base_url": "https://api.together.xyz/v1",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_post_json_retries_on_429_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = post_json_with_retries(
        "https://example.test/v1/chat",
        headers={"Authorization": "Bearer x"},
        payload={"a": 1},
        timeout=5.0,
        max_retries=2,
        error_code="llm_provider_error",
        error_message="failed",
        client=client,
    )
    assert response.status_code == 200
    assert calls["count"] == 2
    client.close()


def test_post_json_does_not_retry_client_errors() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AppError) as exc:
        post_json_with_retries(
            "https://example.test/v1/chat",
            headers={"Authorization": "Bearer x"},
            payload={"a": 1},
            timeout=5.0,
            max_retries=3,
            error_code="llm_provider_error",
            error_message="failed",
            client=client,
        )
    assert exc.value.status_code == 502
    assert calls["count"] == 1
    client.close()


def test_post_json_exhausts_retries_on_5xx() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(503, json={"error": "unavailable"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AppError) as exc:
        post_json_with_retries(
            "https://example.test/v1/embeddings",
            headers={"Authorization": "Bearer x"},
            payload={"input": ["hi"]},
            timeout=5.0,
            max_retries=2,
            error_code="embedding_provider_error",
            error_message="Failed to generate embeddings from Together.ai",
            client=client,
        )
    assert exc.value.code == "embedding_provider_error"
    assert calls["count"] == 3
    client.close()


def test_together_llm_complete_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Answer from [Source 1]."}},
                ]
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TogetherLLMProvider(_settings(), client=client)
    result = provider.complete([LLMMessage(role="user", content="Hello")])
    assert result.content == "Answer from [Source 1]."
    assert result.model == "test-chat-model"
    assert result.latency_ms >= 0
    client.close()


def test_together_embedding_parses_ordered_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0, 0.0]},
                ]
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TogetherEmbeddingProvider(_settings(), client=client)
    vectors = provider.embed_documents(["a", "b"])
    assert vectors == [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]
    client.close()


def test_together_requires_api_key() -> None:
    with pytest.raises(AppError) as exc:
        TogetherLLMProvider(_settings(together_api_key=""))
    assert exc.value.code == "missing_together_api_key"


def test_build_embedding_provider_fake_implements_interface() -> None:
    from app.ingestion.embeddings import build_embedding_provider

    provider = build_embedding_provider(_settings(embedding_provider="fake", app_env="development"))
    assert provider.dimensions == 4
    docs = provider.embed_documents(["alpha", "beta"])
    assert len(docs) == 2
    assert len(docs[0]) == 4
    query = provider.embed_query("alpha")
    assert len(query) == 4


def test_build_embedding_provider_together_without_key_fails() -> None:
    from app.ingestion.embeddings import build_embedding_provider

    with pytest.raises(AppError) as exc:
        build_embedding_provider(
            _settings(
                embedding_provider="together",
                app_env="development",
                together_api_key="",
            )
        )
    assert exc.value.code == "missing_together_api_key"


def test_build_llm_provider_fake() -> None:
    from app.llm.factory import build_llm_provider

    provider = build_llm_provider(_settings(llm_provider="fake", app_env="development"))
    response = provider.complete([LLMMessage(role="user", content="hello")])
    assert response.content
    assert response.model
