"""Search, retrieval, and RAG conversation tests."""

from __future__ import annotations

from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.llm.fake import FakeLLMProvider
from app.llm.prompts import build_grounded_messages
from app.models.chunk import DocumentChunk
from app.retrieval.scoring import ScoredChunk, cosine_similarity


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_policy(
    client: TestClient,
    admin_token: str,
    text: str,
    title: str = "PTO Policy",
) -> dict:
    response = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": title, "department": "HR", "category": "Benefits"},
        files={"file": ("policy.txt", BytesIO(text.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["processing_status"] == "completed"
    return response.json()


def test_cosine_similarity_identical_vectors() -> None:
    vector = [0.0, 1.0, 0.0]
    assert cosine_similarity(vector, vector) == 1.0


def test_traditional_search_by_keyword(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload_policy(
        client,
        admin_token,
        "Employees receive twenty days of paid time off each calendar year.",
    )
    response = client.get(
        "/api/v1/search",
        headers=_auth(employee_token),
        params={"q": "paid time off", "department": "HR"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert any("PTO" in item["title"] for item in payload["items"])


def test_semantic_search_returns_hits(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload_policy(
        client,
        admin_token,
        "The company PTO policy grants twenty days of paid time off annually.",
    )
    response = client.post(
        "/api/v1/search/semantic",
        headers=_auth(employee_token),
        json={"query": "How many PTO days do employees get?", "department": "HR"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["hits"]
    assert payload["hits"][0]["document_title"] == "PTO Policy"
    assert "relevance_score" in payload["hits"][0]


def test_rag_answer_with_citations(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload_policy(
        client,
        admin_token,
        "Company PTO policy: employees receive twenty days of paid time off each year.",
    )
    created = client.post(
        "/api/v1/conversations",
        headers=_auth(employee_token),
        json={"title": "PTO questions"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    asked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(employee_token),
        json={"content": "What is the company PTO policy for paid time off days?"},
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assistant = body["assistant_message"]
    assert assistant["role"] == "assistant"
    assert assistant["insufficient_context"] is False
    assert assistant["grounded"] is True
    assert assistant["citations"]
    citation = assistant["citations"][0]
    assert citation["document_title"] == "PTO Policy"
    assert citation["chunk_id"] is not None
    assert citation["relevance_score"] > 0
    assert "page_number" in citation
    assert "twenty days" in assistant["content"].lower()
    assert "chunk_id" not in assistant["content"].lower()
    assert "title=" not in assistant["content"]
    assert assistant["retrieval"]["supporting_chunks"] >= 1


def test_retrieval_ranks_relevant_chunk_higher(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload_policy(
        client,
        admin_token,
        "Employees receive twenty days of paid time off each calendar year.",
        title="PTO Policy",
    )
    _upload_policy(
        client,
        admin_token,
        "Forklift operators must wear safety helmets in the warehouse.",
        title="Safety Manual",
    )
    response = client.post(
        "/api/v1/search/semantic",
        headers=_auth(employee_token),
        json={"query": "How many paid time off days do employees receive?"},
    )
    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    assert hits
    assert hits[0]["document_title"] == "PTO Policy"
    assert hits[0]["relevance_score"] >= hits[-1]["relevance_score"]


def test_insufficient_context_refuses_when_no_documents(
    client: TestClient,
    employee_token: str,
) -> None:
    created = client.post(
        "/api/v1/conversations",
        headers=_auth(employee_token),
        json={},
    )
    conversation_id = created.json()["id"]
    asked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(employee_token),
        json={"content": "What is the company PTO policy?"},
    )
    assert asked.status_code == 200, asked.text
    assistant = asked.json()["assistant_message"]
    assert assistant["insufficient_context"] is True
    assert assistant["grounded"] is False
    assert assistant["citations"] == []
    assert "couldn't find enough information" in assistant["content"].lower()


def test_insufficient_context_refuses_below_threshold(
    client: TestClient,
    admin_token: str,
    employee_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RETRIEVAL_MIN_SCORE", "0.99")
    get_settings.cache_clear()

    _upload_policy(
        client,
        admin_token,
        "Forklift operators must wear safety helmets in the warehouse.",
        title="Safety Manual",
    )
    created = client.post(
        "/api/v1/conversations",
        headers=_auth(employee_token),
        json={},
    )
    conversation_id = created.json()["id"]
    asked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(employee_token),
        json={"content": "What is the completely unrelated quantum finance policy xyzzy?"},
    )
    assert asked.status_code == 200, asked.text
    assistant = asked.json()["assistant_message"]
    assert assistant["insufficient_context"] is True
    assert assistant["citations"] == []
    assert "couldn't find enough information" in assistant["content"].lower()


def test_conversation_isolation(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    created = client.post(
        "/api/v1/conversations",
        headers=_auth(employee_token),
        json={"title": "Private"},
    )
    conversation_id = created.json()["id"]

    admin_view = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth(admin_token),
    )
    assert admin_view.status_code == 200

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "password": "password123",
            "full_name": "Other User",
        },
    )
    other_token = register.json()["access_token"]
    denied = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth(other_token),
    )
    assert denied.status_code == 404

    ask_denied = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(other_token),
        json={"content": "Can I ask here?"},
    )
    assert ask_denied.status_code == 404

    delete_denied = client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth(other_token),
    )
    assert delete_denied.status_code == 404


def test_ask_surfaces_llm_provider_failure(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    from app.core.exceptions import AppError
    from app.llm.base import LLMMessage, LLMResponse
    from app.llm.factory import get_llm_provider

    upload = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": "PTO", "department": "HR", "category": "Benefits"},
        files={
            "file": (
                "pto.txt",
                BytesIO(b"Employees receive twenty days of paid time off each year."),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201

    class FailingLLM:
        model_name = "failing-llm"

        def complete(self, messages: list[LLMMessage]) -> LLMResponse:
            raise AppError(
                "Upstream LLM unavailable",
                status_code=502,
                code="llm_provider_error",
            )

    app = client.app
    app.dependency_overrides[get_llm_provider] = lambda: FailingLLM()
    try:
        created = client.post(
            "/api/v1/conversations",
            headers=_auth(employee_token),
            json={"title": "LLM fail"},
        )
        conversation_id = created.json()["id"]
        asked = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            headers=_auth(employee_token),
            json={"content": "How many PTO days do employees receive?"},
        )
        assert asked.status_code == 502
        assert asked.json()["code"] == "llm_provider_error"
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_build_grounded_messages_marks_insufficient() -> None:
    messages = build_grounded_messages("question", [], insufficient_context=True)
    assert messages[0].role == "system"
    assert "INSUFFICIENT_CONTEXT" in messages[0].content


def test_fake_llm_uses_source_context() -> None:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_index=0,
        content="Employees receive twenty days of PTO.",
        page_number=1,
        char_count=40,
        embedding=[0.1] * 768,
    )
    scored = [
        ScoredChunk(
            chunk=chunk,
            score=0.9,
            document_title="PTO Policy",
            department="HR",
            category="Benefits",
        )
    ]
    messages = build_grounded_messages(
        "How many PTO days?",
        scored,
        insufficient_context=False,
    )
    response = FakeLLMProvider().complete(messages)
    assert "twenty days" in response.content.lower()
    assert "chunk_id" not in response.content.lower()
    assert "title=" not in response.content
