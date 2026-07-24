"""Unit tests for password hashing and JWT helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.models.enums import UserRole
from app.security.passwords import hash_password, verify_password
from app.security.tokens import TokenError, create_access_token, decode_access_token


def test_password_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_roundtrip() -> None:
    settings = get_settings()
    user_id = uuid4()
    token, expires_at = create_access_token(
        subject=user_id,
        role=UserRole.ADMIN,
        settings=settings,
    )
    payload = decode_access_token(token, settings)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert expires_at.tzinfo is not None


def test_decode_rejects_tampered_token() -> None:
    settings = get_settings()
    token, _ = create_access_token(
        subject=uuid4(),
        role=UserRole.EMPLOYEE,
        settings=settings,
    )
    with pytest.raises(TokenError):
        decode_access_token(token + "x", settings)
