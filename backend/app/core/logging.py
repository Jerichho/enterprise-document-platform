"""Structured logging configuration."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.request_context import get_request_id

_SECRET_ASSIGN_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*([^\s,;]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer)\s+(\S+)")


def configure_logging(level: str = "INFO", *, log_format: str = "json") -> None:
    """Configure root logging with text or JSON structured output."""
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
                handler.addFilter(RequestIdFilter())
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt=(
                    "%(asctime)s | %(levelname)s | %(name)s | "
                    "request_id=%(request_id)s | %(message)s"
                ),
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestIdFilter(logging.Filter):
    """Inject the current request_id from contextvars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log line for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": redact_secrets(record.getMessage()),
        }
        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def redact_secrets(value: str) -> str:
    """Mask common secret assignments and Bearer tokens in log text."""
    redacted = _BEARER_PATTERN.sub(r"\1 [REDACTED]", value)
    return _SECRET_ASSIGN_PATTERN.sub(r"\1=[REDACTED]", redacted)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger."""
    return logging.getLogger(name)


def bind_request_id(logger: logging.Logger, request_id: str) -> logging.LoggerAdapter[Any]:
    """Attach a request_id to subsequent log calls."""
    return logging.LoggerAdapter(logger, extra={"request_id": request_id})
