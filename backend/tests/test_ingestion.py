"""Ingestion pipeline unit and integration tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.ingestion.chunking import chunk_segments
from app.ingestion.cleaning import clean_text
from app.ingestion.embeddings.fake import FakeEmbeddingProvider
from app.ingestion.extraction import TextSegment, extract_text
from app.models.enums import DocumentFileType
from app.repositories.chunk_repository import ChunkRepository


def test_clean_text_normalizes_whitespace() -> None:
    raw = "Hello   world\r\n\r\n\r\nNext"
    assert clean_text(raw) == "Hello world\n\nNext"


def test_chunk_segments_overlap() -> None:
    segments = [TextSegment(text="abcdefghij", page_number=1)]
    chunks = chunk_segments(segments, chunk_size=4, chunk_overlap=2)
    assert [chunk.content for chunk in chunks] == ["abcd", "cdef", "efgh", "ghij"]
    assert all(chunk.page_number == 1 for chunk in chunks)


def test_chunk_preserves_dominant_page() -> None:
    segments = [
        TextSegment(text="AAAA", page_number=1),
        TextSegment(text="BBBBBBBB", page_number=2),
    ]
    chunks = chunk_segments(segments, chunk_size=8, chunk_overlap=0)
    assert chunks
    assert chunks[0].page_number in {1, 2}


def test_extract_txt() -> None:
    segments = extract_text(b"PTO is 20 days.", DocumentFileType.TXT)
    assert len(segments) == 1
    assert "PTO" in segments[0].text


def test_extract_blank_pdf_raises_empty() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(AppError) as exc:
        extract_text(buffer.getvalue(), DocumentFileType.PDF)
    assert exc.value.code == "empty_extraction"


def test_extract_pdf_with_text() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sample_pto.pdf"
    segments = extract_text(fixture.read_bytes(), DocumentFileType.PDF)
    assert len(segments) == 1
    assert segments[0].page_number == 1
    assert "twenty days" in segments[0].text.lower()


def test_extract_docx() -> None:
    document = DocxDocument()
    document.add_paragraph("Expense reports are due monthly.")
    buffer = BytesIO()
    document.save(buffer)
    segments = extract_text(buffer.getvalue(), DocumentFileType.DOCX)
    assert "Expense reports" in segments[0].text


def test_fake_embeddings_are_deterministic() -> None:
    provider = FakeEmbeddingProvider(dimensions=32)
    first = provider.embed_query("policy")
    second = provider.embed_query("policy")
    assert first == second
    assert len(first) == 32
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_upload_creates_chunks(
    client: TestClient,
    admin_token: str,
    db_session: Session,
) -> None:
    content = ("Company remote work policy. " * 40).strip()
    response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Remote Work", "department": "HR", "category": "Policy"},
        files={"file": ("remote.txt", BytesIO(content.encode()), "text/plain")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["processing_status"] == "completed"
    assert body["latest_ingestion_job"]["status"] == "completed"

    chunks = ChunkRepository(db_session).list_for_document(UUID(body["id"]))
    assert len(chunks) >= 1
    assert chunks[0].embedding
    assert len(chunks[0].embedding) == get_settings().embedding_dimensions
    assert "remote work" in chunks[0].content.lower() or "Remote" in chunks[0].content


def test_failed_ingestion_on_empty_txt(
    client: TestClient,
    admin_token: str,
) -> None:
    # Validation rejects empty files before ingestion.
    response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"title": "Empty", "department": "IT", "category": "Other"},
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "empty_file"


def test_ingestion_fails_when_embedding_provider_errors(
    client: TestClient,
    admin_token: str,
) -> None:
    from app.core.exceptions import AppError
    from app.ingestion.embeddings import get_embedding_provider

    class FailingEmbeddings:
        dimensions = 768

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise AppError(
                "Embedding upstream failed",
                status_code=502,
                code="embedding_provider_error",
            )

        def embed_query(self, text: str) -> list[float]:
            raise AppError(
                "Embedding upstream failed",
                status_code=502,
                code="embedding_provider_error",
            )

    app = client.app
    app.dependency_overrides[get_embedding_provider] = lambda: FailingEmbeddings()
    try:
        response = client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"title": "Embed Fail", "department": "IT", "category": "Other"},
            files={
                "file": (
                    "fail.txt",
                    BytesIO(b"Content that should fail embedding."),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["processing_status"] == "failed"
        assert body["ingestion_stage"] == "failed"
        assert body["latest_ingestion_job"]["status"] == "failed"
        assert "Embedding" in (body["processing_error"] or "")
    finally:
        app.dependency_overrides.pop(get_embedding_provider, None)
