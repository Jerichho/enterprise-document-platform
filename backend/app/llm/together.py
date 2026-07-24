"""Together.ai chat-completions LLM provider."""

from __future__ import annotations

import time

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.provider_http import post_json_with_retries
from app.llm.base import LLMMessage, LLMResponse


class TogetherLLMProvider:
    """Generate grounded answers via Together.ai chat completions."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        if not settings.together_api_key:
            raise AppError(
                "TOGETHER_API_KEY is required for the Together LLM provider",
                status_code=500,
                code="missing_together_api_key",
            )
        self._settings = settings
        self._client = client

    @property
    def model_name(self) -> str:
        return self._settings.together_model

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        url = f"{self._settings.together_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.together_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.together_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": 0.1,
        }
        started = time.perf_counter()
        response = post_json_with_retries(
            url,
            headers=headers,
            payload=payload,
            timeout=float(self._settings.llm_request_timeout_seconds),
            max_retries=self._settings.llm_max_retries,
            error_code="llm_provider_error",
            error_message="Failed to generate an answer from Together.ai",
            client=self._client,
        )
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise AppError(
                "LLM provider returned no choices",
                status_code=502,
                code="llm_empty_response",
            )
        content = choices[0]["message"]["content"]
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(
            content=str(content).strip(),
            model=self._settings.together_model,
            latency_ms=latency_ms,
        )
