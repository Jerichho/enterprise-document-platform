"""Answer quality, refusal, and presentation-focused RAG tests."""

from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.llm.answer_sanitize import sanitize_answer_text
from app.llm.fake import FakeLLMProvider
from app.llm.prompts import build_grounded_messages
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.retrieval.evidence import select_supporting_evidence
from app.retrieval.scoring import ScoredChunk


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload(
    client: TestClient,
    admin_token: str,
    *,
    text: str,
    title: str,
    department: str = "HR",
    category: str = "Benefits",
) -> dict:
    response = client.post(
        "/api/v1/documents",
        headers=_auth(admin_token),
        data={"title": title, "department": department, "category": category},
        files={"file": (f"{title}.txt", BytesIO(text.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ask(client: TestClient, token: str, question: str) -> dict:
    created = client.post("/api/v1/conversations", headers=_auth(token), json={})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    asked = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth(token),
        json={"content": question},
    )
    assert asked.status_code == 200, asked.text
    return asked.json()["assistant_message"]


def test_prompt_excludes_raw_metadata_fields() -> None:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_index=0,
        content="Employees receive twenty days of paid time off each year.",
        page_number=1,
        char_count=60,
        embedding=[0.1] * 768,
    )
    scored = [
        ScoredChunk(
            chunk=chunk,
            score=0.91,
            document_title="PTO Policy",
            department="HR",
            category="Benefits",
        )
    ]
    messages = build_grounded_messages("How many PTO days?", scored, insufficient_context=False)
    system = messages[0].content
    assert "chunk_id=" not in system
    assert "score=" not in system
    assert "title=" not in system
    assert "<document>" in system
    assert "Content:" in system
    assert "Return only the answer text" in messages[1].content


def test_fake_llm_answer_is_clean_and_concise() -> None:
    chunk = DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_index=0,
        content="Employees receive twenty days of paid time off each year.",
        page_number=1,
        char_count=60,
        embedding=[0.1] * 768,
    )
    scored = [
        ScoredChunk(
            chunk=chunk,
            score=0.91,
            document_title="PTO Policy",
            department="HR",
            category="Benefits",
        )
    ]
    messages = build_grounded_messages(
        "How many PTO days do employees receive?",
        scored,
        insufficient_context=False,
    )
    response = FakeLLMProvider().complete(messages)
    content = response.content.lower()
    assert "twenty days" in content
    assert "chunk_id" not in content
    assert "title=" not in content
    assert "department=" not in content
    assert "score=" not in content
    assert "based on the provided documents" not in content
    assert "source 1" not in content
    assert len(response.content) < 500


def test_sanitize_strips_metadata_leakage() -> None:
    dirty = (
        "Based on the provided documents: title='PTO Policy'; department=HR; "
        "chunk_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee; score=0.458 Employees "
        "receive twenty days (see Source 1)."
    )
    cleaned = sanitize_answer_text(dirty)
    assert "title=" not in cleaned
    assert "chunk_id" not in cleaned.lower()
    assert "aaaaaaaa-bbbb" not in cleaned
    assert "score=" not in cleaned
    assert "Source 1" not in cleaned
    assert "twenty days" in cleaned.lower()


def test_low_relevance_returns_insufficient_context() -> None:
    decision = select_supporting_evidence(
        [
            ScoredChunk(
                chunk=DocumentChunk(
                    id=uuid4(),
                    document_id=uuid4(),
                    document_version_id=uuid4(),
                    chunk_index=0,
                    content="Warehouse forklift operators must wear helmets.",
                    page_number=1,
                    char_count=50,
                    embedding=[0.1] * 768,
                ),
                score=0.458,
                document_title="Safety Manual",
                department="Ops",
                category="Safety",
            )
        ],
        question="How should employees report a phishing attempt?",
        min_score=0.50,
        min_supporting_chunks=1,
        min_term_overlap=1,
    )
    assert decision.insufficient is True
    assert decision.supporting == []


def test_lexical_boost_allows_relevant_mid_score_chunk() -> None:
    decision = select_supporting_evidence(
        [
            ScoredChunk(
                chunk=DocumentChunk(
                    id=uuid4(),
                    document_id=uuid4(),
                    document_version_id=uuid4(),
                    chunk_index=0,
                    content=(
                        "Suspected phishing or malware must be reported to "
                        "security@example.com within one business hour."
                    ),
                    page_number=1,
                    char_count=100,
                    embedding=[0.1] * 768,
                ),
                score=0.42,
                document_title="Cybersecurity Policy",
                department="IT",
                category="Security",
            )
        ],
        question="How should employees report a phishing attempt?",
        min_score=0.50,
        min_supporting_chunks=1,
        min_term_overlap=1,
    )
    assert decision.insufficient is False
    assert len(decision.supporting) == 1


def test_unrelated_document_not_used_for_grounded_answer(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload(
        client,
        admin_token,
        text="Employees receive twenty days of paid time off each calendar year.",
        title="PTO Policy",
    )
    assistant = _ask(
        client,
        employee_token,
        "How should employees report a phishing attempt?",
    )
    assert assistant["insufficient_context"] is True
    assert assistant["grounded"] is False
    assert assistant["citations"] == []
    assert assistant["answer_status"] == "insufficient_context"
    assert "couldn't find enough information" in assistant["content"].lower()
    assert "chunk_id" not in assistant["content"].lower()
    assert "title=" not in assistant["content"]


def test_relevant_context_produces_concise_answer_with_structured_citations(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload(
        client,
        admin_token,
        text=(
            "Company PTO policy: employees receive twenty days of paid time off "
            "each year. Unused PTO may be carried over up to five days."
        ),
        title="PTO Policy",
    )
    assistant = _ask(
        client,
        employee_token,
        "How many PTO days do employees receive?",
    )
    assert assistant["insufficient_context"] is False
    assert assistant["grounded"] is True
    assert assistant["citations"]
    assert assistant["citations"][0]["document_title"] == "PTO Policy"
    assert "retrieval" in assistant
    assert assistant["retrieval"]["supporting_chunks"] >= 1
    content = assistant["content"]
    assert "twenty" in content.lower()
    assert "chunk_id" not in content.lower()
    assert "title=" not in content
    assert "Based on the provided documents" not in content


def test_cybersecurity_question_cites_security_policy(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload(
        client,
        admin_token,
        text=(
            "Suspected phishing or malware must be reported to security@example.com "
            "within one business hour of discovery."
        ),
        title="Cybersecurity Policy",
        department="IT",
        category="Security",
    )
    assistant = _ask(
        client,
        employee_token,
        "How should employees report a phishing attempt?",
    )
    assert assistant["grounded"] is True
    assert assistant["citations"][0]["document_title"] == "Cybersecurity Policy"
    assert "security@example.com" in assistant["content"].lower()
    assert "chunk_id" not in assistant["content"].lower()


def test_parking_question_refuses_without_parking_policy(
    client: TestClient,
    admin_token: str,
    employee_token: str,
) -> None:
    _upload(
        client,
        admin_token,
        text="Employees receive twenty days of paid time off each calendar year.",
        title="PTO Policy",
    )
    assistant = _ask(client, employee_token, "What is the company parking policy?")
    assert assistant["insufficient_context"] is True
    assert assistant["citations"] == []


def test_embedding_provider_stored_on_document(
    client: TestClient,
    admin_token: str,
) -> None:
    doc = _upload(
        client,
        admin_token,
        text="Employees receive twenty days of paid time off each calendar year.",
        title="PTO Policy",
    )
    detail = client.get(f"/api/v1/documents/{doc['id']}", headers=_auth(admin_token))
    assert detail.status_code == 200
    body = detail.json()
    assert body["embedding_provider"] == "fake"
    assert body["embedding_model"]


def test_embedding_provider_mismatch_excludes_stale_vectors(
    client: TestClient,
    admin_token: str,
    employee_token: str,
    db_session,
) -> None:
    doc = _upload(
        client,
        admin_token,
        text="Employees receive twenty days of paid time off each calendar year.",
        title="PTO Policy",
    )
    db_session.expire_all()
    row = db_session.get(Document, UUID(doc["id"]))
    assert row is not None
    row.embedding_provider = "together"
    row.embedding_model = "togethercomputer/m2-bert-80M-8k-retrieval"
    db_session.commit()

    assistant = _ask(client, employee_token, "How many PTO days do employees receive?")
    assert assistant["insufficient_context"] is True
    assert assistant["embedding_provider_mismatch"] is True
    assert "PTO Policy" in assistant["mismatched_documents"]


def test_switching_provider_requires_reprocess_message(
    client: TestClient,
    admin_token: str,
    employee_token: str,
    db_session,
) -> None:
    doc = _upload(
        client,
        admin_token,
        text="Phishing must be reported to security@example.com.",
        title="Cybersecurity Policy",
        department="IT",
        category="Security",
    )
    db_session.expire_all()
    row = db_session.get(Document, UUID(doc["id"]))
    assert row is not None
    row.embedding_provider = "together"
    db_session.commit()

    assistant = _ask(
        client,
        employee_token,
        "How should employees report a phishing attempt?",
    )
    assert assistant["insufficient_context"] is True
    assert assistant["embedding_provider_mismatch"] is True


def test_ready_reports_demo_mode(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    payload = response.json()
    assert "demo_mode" in payload
    assert payload["llm_provider"] == "fake"
    assert payload["embedding_provider"] == "fake"
