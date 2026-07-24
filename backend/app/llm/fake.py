"""Deterministic fake LLM for tests (never calls paid APIs)."""

from __future__ import annotations

import re
import time

from app.llm.base import LLMMessage, LLMResponse

_INSUFFICIENT = (
    "I couldn't find enough information in the indexed documents to answer that question."
)

_METADATA_LINE = re.compile(
    r"^(title|department|page|chunk_id|score|relevance)\s*[=:].+$",
    re.IGNORECASE,
)


class FakeLLMProvider:
    """Grounded stub that answers only from supplied context blocks."""

    def __init__(self, model_name: str = "fake-llm") -> None:
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        started = time.perf_counter()
        system = next((m.content for m in messages if m.role == "system"), "")
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")

        if "INSUFFICIENT_CONTEXT" in system:
            content = _INSUFFICIENT
        else:
            content = self._answer_from_context(system, user)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(content=content, model=self._model_name, latency_ms=latency_ms)

    def _answer_from_context(self, system: str, user: str) -> str:
        documents = re.findall(
            r"<document>\s*(.*?)\s*</document>",
            system,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Backward-compatible fallback for older [Source N] prompts in unit tests.
        if not documents:
            legacy = re.findall(
                r"\[Source (\d+)\](.*?)(?=\[Source \d+\]|\Z)",
                system,
                flags=re.DOTALL,
            )
            documents = [body for _, body in legacy]

        if not documents:
            return _INSUFFICIENT

        question = user
        if "Question:" in user:
            question = user.split("Question:", 1)[1]
        question = question.split("Return only", 1)[0].strip()
        question_terms = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", question)}

        best_content: str | None = None
        best_hits = -1
        for body in documents:
            content = self._extract_content(body)
            content_l = content.lower()
            hits = sum(1 for term in question_terms if term in content_l)
            if hits > best_hits:
                best_hits = hits
                best_content = content

        if best_content is None or best_hits == 0:
            return _INSUFFICIENT

        return self._concise_answer(best_content, question_terms)

    @staticmethod
    def _extract_content(body: str) -> str:
        match = re.search(r"Content:\s*(.*)$", body, flags=re.DOTALL | re.IGNORECASE)
        raw = match.group(1) if match else body
        lines: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _METADATA_LINE.match(stripped):
                continue
            if stripped.lower().startswith(("title:", "page:", "department:")):
                continue
            lines.append(stripped)
        return " ".join(lines).strip()

    @staticmethod
    def _concise_answer(content: str, question_terms: set[str]) -> str:
        """Return a short natural-language answer without dumping the full chunk."""
        cleaned = " ".join(content.split())
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if not sentences:
            return cleaned[:280].strip()

        ranked = sorted(
            sentences,
            key=lambda sentence: sum(1 for term in question_terms if term in sentence.lower()),
            reverse=True,
        )
        selected: list[str] = []
        total = 0
        for sentence in ranked:
            hits = sum(1 for term in question_terms if term in sentence.lower())
            if selected and hits == 0:
                continue
            selected.append(sentence)
            total += len(sentence)
            if len(selected) >= 2 or total >= 240:
                break
        answer = " ".join(selected).strip() or ranked[0]
        if len(answer) > 400:
            answer = answer[:397].rstrip() + "..."
        return answer
