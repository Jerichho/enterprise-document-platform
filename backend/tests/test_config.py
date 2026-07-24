"""Configuration and settings tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings, get_settings


def test_cors_origin_list_parsing() -> None:
    settings = Settings(cors_origins="http://localhost:5173, http://localhost:3000")
    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://localhost:3000",
    ]


def test_get_settings_returns_cached_instance() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second


def test_default_providers_are_fake_for_safe_local_boot() -> None:
    settings = Settings(
        secret_key="test-secret-key-at-least-16-chars",
        _env_file=None,
    )
    assert settings.embedding_provider == "fake"
    assert settings.llm_provider == "fake"
    assert settings.embedding_dimensions == 768
    assert settings.chunk_size > settings.chunk_overlap


def test_production_rejects_insecure_defaults() -> None:
    settings = Settings(
        app_env="production",
        secret_key="change-me-to-a-long-random-string-in-production",
        database_url="postgresql+psycopg://ekp:ekp_secret@localhost:5432/ekp",
        _env_file=None,
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.assert_secure_for_environment()


def test_production_accepts_strong_secrets() -> None:
    settings = Settings(
        app_env="production",
        secret_key="a-sufficiently-long-production-secret-key-value",
        database_url="postgresql+psycopg://ekp:not_the_default@localhost:5432/ekp",
        _env_file=None,
    )
    settings.assert_secure_for_environment()
