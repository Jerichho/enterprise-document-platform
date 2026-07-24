"""Health and readiness endpoint tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.logging import redact_secrets
from app.schemas.health import DependencyStatus


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "service" in payload
    assert "version" in payload
    assert payload["environment"] == "test"
    assert "X-Request-ID" in response.headers
    assert "X-Response-Time-Ms" in response.headers


def test_health_preserves_incoming_request_id(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-correlation-id"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-correlation-id"


def test_api_v1_status(client: TestClient) -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api": "v1"}


def test_ready_when_dependencies_available(client: TestClient) -> None:
    with (
        patch("app.api.v1.system.check_database_connection", return_value=True),
        patch(
            "app.api.v1.system.check_pgvector_extension",
            return_value=(True, "vector extension installed"),
        ),
        patch(
            "app.api.v1.system._storage_status",
            return_value=DependencyStatus(name="storage", status="ok", detail="ok"),
        ),
    ):
        response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["environment"] == "test"
    assert payload["version"]
    names = {check["name"] for check in payload["checks"]}
    assert names >= {"database", "pgvector", "storage", "llm_provider", "embedding_provider"}


def test_ready_when_database_unavailable(client: TestClient) -> None:
    with (
        patch("app.api.v1.system.check_database_connection", return_value=False),
        patch(
            "app.api.v1.system.check_pgvector_extension",
            return_value=(False, "Unable to verify pgvector extension"),
        ),
        patch(
            "app.api.v1.system._storage_status",
            return_value=DependencyStatus(name="storage", status="ok", detail="ok"),
        ),
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"][0]["status"] == "unavailable"


def test_ready_degraded_when_provider_misconfigured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LLM_PROVIDER", "together")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "together")
    monkeypatch.setenv("TOGETHER_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    with (
        patch("app.api.v1.system.check_database_connection", return_value=True),
        patch(
            "app.api.v1.system.check_pgvector_extension",
            return_value=(True, "vector extension installed"),
        ),
        patch(
            "app.api.v1.system._storage_status",
            return_value=DependencyStatus(name="storage", status="ok", detail="ok"),
        ),
    ):
        response = client.get("/ready")

    get_settings.cache_clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    by_name = {item["name"]: item for item in payload["checks"]}
    assert by_name["llm_provider"]["status"] == "degraded"
    assert by_name["embedding_provider"]["status"] == "degraded"
    assert "sk-" not in (by_name["llm_provider"]["detail"] or "")


def test_redact_secrets_masks_sensitive_assignments() -> None:
    text = "Authorization: Bearer secret-token TOGETHER_API_KEY=abc123 password=hunter2"
    redacted = redact_secrets(text)
    assert "abc123" not in redacted
    assert "hunter2" not in redacted
    assert "secret-token" not in redacted
    assert "[REDACTED]" in redacted
