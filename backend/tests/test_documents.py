"""Document API and file-validation tests."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.file_validation import validate_upload
from app.storage.local import LocalStorageService


def _txt_file(
    content: str = "Company PTO policy: 20 days.",
    name: str = "pto.txt",
) -> tuple[str, BytesIO, str]:
    return name, BytesIO(content.encode("utf-8")), "text/plain"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_validate_rejects_unsupported_extension() -> None:
    settings = Settings(secret_key="test-secret-key-at-least-16-chars", upload_max_size_mb=1)
    with pytest.raises(AppError) as exc:
        validate_upload(
            filename="malware.exe",
            content_type="application/octet-stream",
            data=b"MZ",
            settings=settings,
        )
    assert exc.value.code == "unsupported_file_type"


def test_validate_rejects_oversized_file() -> None:
    settings = Settings(secret_key="test-secret-key-at-least-16-chars", upload_max_size_mb=1)
    data = b"x" * (1024 * 1024 + 1)
    with pytest.raises(AppError) as exc:
        validate_upload(
            filename="big.txt",
            content_type="text/plain",
            data=data,
            settings=settings,
        )
    assert exc.value.code == "file_too_large"


def test_validate_rejects_invalid_pdf_magic() -> None:
    settings = Settings(secret_key="test-secret-key-at-least-16-chars")
    with pytest.raises(AppError) as exc:
        validate_upload(
            filename="fake.pdf",
            content_type="application/pdf",
            data=b"not-a-pdf",
            settings=settings,
        )
    assert exc.value.code == "invalid_pdf"


def test_local_storage_roundtrip(tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    storage.save(key="docs/a.txt", data=b"hello", content_type="text/plain")
    assert storage.exists("docs/a.txt")
    assert storage.read("docs/a.txt") == b"hello"
    storage.delete("docs/a.txt")
    assert not storage.exists("docs/a.txt")


def test_local_storage_rejects_path_traversal(tmp_path) -> None:
    storage = LocalStorageService(tmp_path)
    with pytest.raises(AppError):
        storage.save(key="../outside.txt", data=b"x", content_type="text/plain")


def test_upload_requires_admin(client: TestClient, employee_token: str) -> None:
    name, buffer, content_type = _txt_file()
    response = client.post(
        "/api/v1/documents",
        headers=_auth(employee_token),
        data={"title": "PTO", "department": "HR", "category": "Policy"},
        files={"file": (name, buffer, content_type)},
    )
    assert response.status_code == 403


def test_upload_list_get_delete_flow(
    client: TestClient,
    admin_token: str,
    employee_token: str,
    storage: LocalStorageService,
) -> None:
    name, buffer, content_type = _txt_file()
    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={
            "title": "PTO Policy",
            "department": "HR",
            "category": "Benefits",
        },
        files={"file": (name, buffer, content_type)},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["title"] == "PTO Policy"
    assert document["processing_status"] == "completed"
    assert document["current_version"] == 1
    assert len(document["versions"]) == 1
    assert document["latest_ingestion_job"]["status"] == "completed"
    assert document["versions"][0]["original_filename"] == "pto.txt"
    assert any(storage._root.rglob("pto.txt"))

    listed = client.get("/api/v1/documents", headers=_auth(employee_token))
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "PTO Policy"

    filtered = client.get(
        "/api/v1/documents",
        headers=_auth(employee_token),
        params={"department": "HR", "q": "PTO"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    detail = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=_auth(employee_token),
    )
    assert detail.status_code == 200
    assert detail.json()["versions"][0]["file_type"] == "txt"

    deleted = client.delete(
        f"/api/v1/documents/{document['id']}",
        headers=_auth(admin_token),
    )
    assert deleted.status_code == 204
    assert (
        client.get(
            f"/api/v1/documents/{document['id']}",
            headers=_auth(employee_token),
        ).status_code
        == 404
    )
    assert not any(storage._root.rglob("pto.txt"))


def test_employee_cannot_delete(client: TestClient, admin_token: str, employee_token: str) -> None:
    name, buffer, content_type = _txt_file(name="policy.txt")
    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Policy", "department": "HR", "category": "Policy"},
        files={"file": (name, buffer, content_type)},
    )
    doc_id = upload.json()["id"]
    response = client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(employee_token))
    assert response.status_code == 403


def test_reprocess_queues_new_job(client: TestClient, admin_token: str) -> None:
    name, buffer, content_type = _txt_file(name="safety.txt")
    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Safety", "department": "Ops", "category": "Safety"},
        files={"file": (name, buffer, content_type)},
    )
    doc_id = upload.json()["id"]
    first_job_id = upload.json()["latest_ingestion_job"]["id"]

    reprocess = client.post(
        f"/api/v1/documents/{doc_id}/reprocess",
        headers=_auth(admin_token),
    )
    assert reprocess.status_code == 200
    body = reprocess.json()
    assert body["processing_status"] == "completed"
    assert body["latest_ingestion_job"]["id"] != first_job_id
    assert body["latest_ingestion_job"]["attempt_number"] == 2
    assert body["latest_ingestion_job"]["status"] == "completed"


def test_upload_rejects_invalid_extension(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Bad", "department": "IT", "category": "Other"},
        files={"file": ("notes.exe", BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_file_type"


def test_upload_rejects_oversized_file(
    client: TestClient,
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOAD_MAX_SIZE_MB", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    data = b"x" * (1024 * 1024 + 1)
    response = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Huge", "department": "IT", "category": "Other"},
        files={"file": ("huge.txt", BytesIO(data), "text/plain")},
    )
    get_settings.cache_clear()
    assert response.status_code == 400
    assert response.json()["code"] == "file_too_large"


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/documents").status_code == 401


def test_upload_exposes_stats_stage_and_preview(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "PTO Policy", "department": "HR", "category": "Benefits"},
        files={"file": _txt_file("Employees receive twenty days of paid time off.")},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["processing_status"] == "completed"
    assert body["ingestion_stage"] == "completed"
    assert body["chunk_count"] >= 1
    assert body["embedding_count"] == body["chunk_count"]
    assert body["uploaded_by"]["email"] == "admin@example.com"
    assert body["file_type"] == "txt"

    preview = client.get(
        f"/api/v1/documents/{body['id']}/preview",
        headers=_auth(employee_token),
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert "twenty days" in preview_body["preview_text"]
    assert preview_body["chunk_count"] >= 1

    employee_view = client.get(
        f"/api/v1/documents/{body['id']}",
        headers=_auth(employee_token),
    )
    assert employee_view.status_code == 200
    # Processing errors are admin-only; completed docs have none either way.
    assert employee_view.json()["processing_error"] is None


def test_keyword_list_search_matches_chunk_content(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "Warehouse Rules", "department": "Ops", "category": "Safety"},
        files={"file": _txt_file("Forklift operators must wear safety helmets.")},
    )
    response = client.get(
        "/api/v1/documents",
        headers=_auth(employee_token),
        params={"q": "forklift"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any(item["title"] == "Warehouse Rules" for item in payload["items"])
