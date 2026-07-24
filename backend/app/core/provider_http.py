"""Shared HTTP helpers for external AI providers with retries."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)


def post_json_with_retries(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
    max_retries: int,
    error_code: str,
    error_message: str,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """POST JSON with retries for timeouts, 429, and 5xx responses.

    Non-retryable 4xx responses fail immediately. Callers may inject an
    ``httpx.Client`` (useful for MockTransport in tests).
    """
    last_error: Exception | None = None
    owns_client = client is None
    active_client = client or httpx.Client(timeout=timeout)

    try:
        for attempt in range(max_retries + 1):
            try:
                response = active_client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "Provider request timed out (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(min(2**attempt, 30))
                    continue
                break
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Provider request failed (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(min(2**attempt, 30))
                    continue
                break

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 2**attempt))
                last_error = AppError(
                    "Provider rate limited the request",
                    status_code=429,
                    code="provider_rate_limited",
                )
                logger.warning(
                    "Provider rate limited (attempt %s/%s); retrying in %.1fs",
                    attempt + 1,
                    max_retries + 1,
                    min(retry_after, 30),
                )
                if attempt < max_retries:
                    time.sleep(min(retry_after, 30))
                    continue
                break

            if response.status_code >= 500:
                last_error = AppError(
                    f"Provider returned HTTP {response.status_code}",
                    status_code=502,
                    code="provider_server_error",
                )
                logger.warning(
                    "Provider server error %s (attempt %s/%s)",
                    response.status_code,
                    attempt + 1,
                    max_retries + 1,
                )
                if attempt < max_retries:
                    time.sleep(min(2**attempt, 30))
                    continue
                break

            if response.status_code >= 400:
                detail = _safe_error_detail(response)
                raise AppError(
                    f"{error_message}: HTTP {response.status_code}{detail}",
                    status_code=502,
                    code=error_code,
                ) from None

            return response

        raise AppError(
            error_message,
            status_code=502,
            code=error_code,
        ) from last_error
    finally:
        if owns_client:
            active_client.close()


def _safe_error_detail(response: httpx.Response) -> str:
    """Return a short, non-sensitive error suffix for logs/clients."""
    try:
        body = response.json()
    except Exception:
        text = (response.text or "").strip()
        if not text:
            return ""
        return f" ({text[:160]})"

    if not isinstance(body, dict):
        return ""
    message = body.get("error") or body.get("message")
    if isinstance(message, dict):
        message = message.get("message") or message.get("type")
    if message is None:
        return ""
    return f" ({str(message)[:160]})"
