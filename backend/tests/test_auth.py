"""Authentication and authorization API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security.passwords import hash_password


def test_register_creates_employee_and_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.user@example.com",
            "password": "securepass1",
            "full_name": "New User",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["email"] == "new.user@example.com"
    assert payload["user"]["role"] == "employee"
    assert payload["user"]["full_name"] == "New User"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    body = {
        "email": "dup@example.com",
        "password": "securepass1",
        "full_name": "First User",
    }
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "full_name": "Short Pass",
        },
    )
    assert response.status_code == 422


def test_login_success(client: TestClient, employee_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["user"]["id"] == str(employee_user.id)


def test_login_invalid_credentials(client: TestClient, employee_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_login_inactive_user(client: TestClient, user_repo: UserRepository) -> None:
    user_repo.create(
        email="inactive@example.com",
        hashed_password=hash_password("password123"),
        full_name="Inactive User",
        is_active=False,
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert response.json()["detail"] == "Invalid email or password"


def test_admin_access_forbidden_writes_audit(
    client: TestClient,
    employee_token: str,
    admin_token: str,
) -> None:
    denied = client.get(
        "/api/v1/admin/access-check",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "forbidden"

    audits = client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert audits.status_code == 200
    assert any(item["action"] == "auth.access_denied" for item in audits.json()["items"])


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(
    client: TestClient,
    employee_token: str,
    employee_user: User,
) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(employee_user.id)
    assert payload["email"] == "employee@example.com"
    assert payload["role"] == "employee"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_admin_access_allowed_for_admin(client: TestClient, admin_token: str) -> None:
    response = client.get(
        "/api/v1/admin/access-check",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "role": "admin"}


def test_admin_access_forbidden_for_employee(client: TestClient, employee_token: str) -> None:
    response = client.get(
        "/api/v1/admin/access-check",
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_email_is_normalized_on_register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Mixed.Case@Example.COM",
            "password": "securepass1",
            "full_name": "Case User",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixed.case@example.com"
