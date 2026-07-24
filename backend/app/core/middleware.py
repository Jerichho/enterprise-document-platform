"""HTTP middleware for correlation IDs, request timing, and rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.request_context import set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID and log request duration for every HTTP call."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_id(request_id)
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        client_ip = request.client.host if request.client else None
        logger.info(
            "%s %s -> %s (%sms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP and route group.

    Suitable for single-instance deployments. Multi-instance production should
    swap this for a shared backend (e.g. Redis) behind the same middleware shape.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or settings.app_env == "test":
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        group = self._group_for_path(request.url.path)
        limit, window = self._limits_for_group(group, settings)
        key = f"{client}:{group}"
        now = time.monotonic()

        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                request_id = getattr(request.state, "request_id", "-")
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please retry shortly.",
                        "code": "rate_limited",
                    },
                    headers={
                        REQUEST_ID_HEADER: str(request_id),
                        "Retry-After": str(int(window)),
                    },
                )
            bucket.append(now)

        return await call_next(request)

    @staticmethod
    def _group_for_path(path: str) -> str:
        if path.startswith("/api/v1/auth"):
            return "auth"
        if path.startswith("/api/v1/documents"):
            return "documents"
        if path.startswith("/api/v1/conversations"):
            return "chat"
        return "default"

    @staticmethod
    def _limits_for_group(group: str, settings: Settings) -> tuple[int, float]:
        mapping = {
            "auth": (settings.rate_limit_auth_per_minute, 60.0),
            "documents": (settings.rate_limit_upload_per_minute, 60.0),
            "chat": (settings.rate_limit_chat_per_minute, 60.0),
            "default": (settings.rate_limit_default_per_minute, 60.0),
        }
        return mapping.get(group, mapping["default"])
