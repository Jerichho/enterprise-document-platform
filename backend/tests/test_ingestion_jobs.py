"""Background ingestion job reliability tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentVersion, IngestionJob
from app.models.enums import (
    DocumentFileType,
    IngestionJobStatus,
    IngestionStage,
    ProcessingStatus,
    UserRole,
)
from app.models.user import User
from app.repositories.document_repository import DocumentRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(client: TestClient, admin_token: str, title: str = "Job Doc") -> str:
    response = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": title, "department": "IT", "category": "Runbook"},
        files={"file": ("job.txt", BytesIO(b"Background job content."), "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _seed_document(db_session: Session, *, title: str) -> tuple[Document, DocumentVersion]:
    user = User(
        email=f"{title.lower().replace(' ', '-')}-{uuid4().hex[:8]}@example.com",
        full_name="Jobs Tester",
        hashed_password="x",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    document = Document(
        title=title,
        department="IT",
        category="Test",
        current_version=1,
        processing_status=ProcessingStatus.PENDING,
        ingestion_stage=IngestionStage.UPLOADED,
        uploaded_by_id=user.id,
    )
    version = DocumentVersion(
        version_number=1,
        storage_key=f"documents/{uuid4()}/seed.txt",
        original_filename="seed.txt",
        file_type=DocumentFileType.TXT,
        content_type="text/plain",
        file_size_bytes=10,
        checksum_sha256="abc",
        uploaded_by_id=user.id,
    )
    document.versions.append(version)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    current = DocumentRepository(db_session).get_current_version(document)
    assert current is not None
    return document, current


def test_claim_ingestion_job_is_idempotent(db_session: Session) -> None:
    repo = DocumentRepository(db_session)
    document, version = _seed_document(db_session, title="Claim Test")
    job = repo.create_ingestion_job(
        document_id=document.id,
        document_version_id=version.id,
        attempt_number=1,
    )
    first = repo.claim_ingestion_job(job.id)
    second = repo.claim_ingestion_job(job.id)
    assert first is not None
    assert first.status == IngestionJobStatus.RUNNING
    assert second is None


def test_fail_stale_ingestion_jobs(db_session: Session) -> None:
    repo = DocumentRepository(db_session)
    document, version = _seed_document(db_session, title="Stale Test")
    document.processing_status = ProcessingStatus.PROCESSING
    document.ingestion_stage = IngestionStage.EMBEDDING
    db_session.add(document)
    db_session.commit()

    job = repo.create_ingestion_job(
        document_id=document.id,
        document_version_id=version.id,
        attempt_number=1,
    )
    claimed = repo.claim_ingestion_job(job.id)
    assert claimed is not None
    claimed.started_at = datetime.now(UTC) - timedelta(hours=2)
    db_session.add(claimed)
    db_session.commit()

    recovered = repo.fail_stale_ingestion_jobs(older_than=datetime.now(UTC) - timedelta(minutes=30))
    assert len(recovered) == 1
    assert recovered[0].status == IngestionJobStatus.FAILED
    refreshed = repo.get_by_id(document.id)
    assert refreshed is not None
    assert refreshed.processing_status == ProcessingStatus.FAILED


def test_document_ingestion_job_history(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    doc_id = _upload(client, admin_token)
    reprocess = client.post(
        f"/api/v1/documents/{doc_id}/reprocess",
        headers=_auth(admin_token),
    )
    assert reprocess.status_code == 200

    admin_history = client.get(
        f"/api/v1/documents/{doc_id}/ingestion-jobs",
        headers=_auth(admin_token),
    )
    assert admin_history.status_code == 200
    payload = admin_history.json()
    assert payload["total"] >= 2
    assert all("duration_ms" in item for item in payload["items"])

    employee_history = client.get(
        f"/api/v1/documents/{doc_id}/ingestion-jobs",
        headers=_auth(employee_token),
    )
    assert employee_history.status_code == 200
    for item in employee_history.json()["items"]:
        assert item["error_message"] is None


def test_admin_recover_stale_endpoint(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    doc_id = _upload(client, admin_token)
    db_session.expire_all()
    repo = DocumentRepository(db_session)
    jobs = repo.list_ingestion_jobs_for_document(UUID(doc_id))
    assert jobs
    job = jobs[0]
    orphan = IngestionJob(
        document_id=job.document_id,
        document_version_id=job.document_version_id,
        status=IngestionJobStatus.RUNNING,
        attempt_number=job.attempt_number + 1,
        started_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(orphan)
    db_session.commit()

    response = client.post(
        "/api/v1/admin/ingestion-jobs/recover-stale",
        headers=_auth(admin_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recovered"] >= 1
    assert body["stale_after_minutes"] >= 1
