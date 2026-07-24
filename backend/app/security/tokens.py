"""JWT access-token helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app.core.config import Settings
from app.models.enums import UserRole


class TokenError(Exception):
    """Raised when a JWT cannot be decoded or validated."""


def create_access_token(
    *,
    subject: UUID,
    role: UserRole,
    settings: Settings,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """Create a signed JWT and return the token with its expiry timestamp."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role.value,
        "exp": expires_at,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate an access token payload."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired access token") from exc

    if payload.get("type") != "access":
        raise TokenError("Invalid token type")
    if "sub" not in payload:
        raise TokenError("Token subject missing")
    return payload
