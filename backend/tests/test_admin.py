"""Admin analytics, audit log, and readiness provider tests."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_analytics_requires_admin(client: TestClient, employee_token: str) -> None:
    response = client.get("/api/v1/admin/analytics", headers=_auth(employee_token))
    assert response.status_code == 403


def test_analytics_from_live_data(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Handbook", "department": "HR", "category": "Policy"},
        files={"file": ("handbook.txt", BytesIO(b"Employee handbook content."), "text/plain")},
    )
    assert upload.status_code == 201

    created = client.post(
        "/api/v1/conversations",
        headers=_auth(employee_token),
        json={"title": "Ask"},
    )
    conversation_id = created.json()["id"]
    asked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(employee_token),
        json={"content": "What is in the employee handbook?"},
    )
    assert asked.status_code == 200
    assistant = asked.json()["assistant_message"]
    assert assistant["embedding_latency_ms"] is not None
    assert assistant["vector_search_latency_ms"] is not None

    response = client.get("/api/v1/admin/analytics", headers=_auth(admin_token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_users"] >= 2
    assert payload["total_documents"] >= 1
    assert payload["total_indexed_chunks"] >= 1
    assert payload["total_conversations"] >= 1
    assert payload["total_questions"] >= 1
    assert payload["completed_ingestion_jobs"] >= 1
    assert payload["average_embedding_latency_ms"] is not None
    assert payload["average_vector_search_latency_ms"] is not None
    assert payload["average_e2e_latency_ms"] is not None
    assert any(item["category"] == "Policy" for item in payload["documents_by_category"])
    assert any(item["name"] == "HR" for item in payload["documents_by_department"])
    assert any(item["title"] == "Handbook" for item in payload["recent_uploads"])
    assert isinstance(payload["questions_over_time"], list)


def test_analytics_date_range_filter(client: TestClient, admin_token: str) -> None:
    response = client.get(
        "/api/v1/admin/analytics",
        headers=_auth(admin_token),
        params={"start": "2099-01-01T00:00:00Z", "end": "2099-01-31T23:59:59Z"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_questions"] == 0
    assert payload["recent_uploads"] == []
    assert payload["questions_over_time"] == []


def test_audit_log_records_login(client: TestClient, admin_token: str) -> None:
    # admin_token fixture already created the user; login again to write an audit row.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert login.status_code == 200

    response = client.get("/api/v1/admin/audit-logs", headers=_auth(admin_token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["action"] == "auth.login" for item in payload["items"])


def test_ingestion_jobs_endpoint(client: TestClient, admin_token: str) -> None:
    client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Safety", "department": "Ops", "category": "Safety"},
        files={"file": ("safety.txt", BytesIO(b"Wear helmets."), "text/plain")},
    )
    response = client.get("/api/v1/admin/ingestion-jobs", headers=_auth(admin_token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["status"] in {"pending", "running", "completed", "failed"}


def test_ready_includes_provider_checks(client: TestClient) -> None:
    response = client.get("/ready")
    # DB may be unavailable in this environment; still expect provider checks present.
    payload = response.json()
    assert "environment" in payload
    assert "version" in payload
    names = {check["name"] for check in payload["checks"]}
    assert names >= {"database", "pgvector", "storage", "llm_provider", "embedding_provider"}
