"""Select supporting evidence for grounded RAG answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.retrieval.scoring import ScoredChunk

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "have",
        "how",
        "what",
        "when",
        "where",
        "who",
        "why",
        "does",
        "did",
        "should",
        "would",
        "could",
        "about",
        "with",
        "from",
        "this",
        "that",
        "they",
        "them",
        "their",
        "into",
        "over",
        "under",
        "each",
        "year",
        "years",
        "days",
        "day",
        "employees",
        "employee",
        "company",
        "policy",
        "policies",
    }
)


@dataclass(frozen=True)
class EvidenceDecision:
    """Result of applying retrieval-quality gates."""

    supporting: list[ScoredChunk]
    insufficient: bool
    max_score: float
    chunks_retrieved: int
    reason: str


def question_terms(question: str) -> set[str]:
    """Extract meaningful lowercase terms from a user question."""
    tokens = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", question)}
    return {term for term in tokens if term not in _STOPWORDS}


def chunk_term_overlap_count(chunk_content: str, terms: set[str]) -> int:
    """Count how many question terms appear in the chunk."""
    if not terms:
        return 0
    content_l = chunk_content.lower()
    return sum(1 for term in terms if term in content_l)


def chunk_has_term_overlap(chunk_content: str, terms: set[str], *, min_overlap: int) -> bool:
    """Return True when the chunk shares enough question terms."""
    if min_overlap <= 0 or not terms:
        return True
    return chunk_term_overlap_count(chunk_content, terms) >= min_overlap


def effective_relevance(score: float, overlap: int) -> float:
    """Blend vector similarity with lexical overlap for evidence gating.

    Distinctive term matches raise the effective score so keyword-aware fake
    embeddings (and weak real matches with clear lexical support) can pass a
    calibrated threshold without accepting unrelated top-k noise.
    """
    boost = min(0.24, 0.08 * max(overlap, 0))
    return min(1.0, score + boost)


def select_supporting_evidence(
    scored: list[ScoredChunk],
    *,
    question: str,
    min_score: float,
    min_supporting_chunks: int,
    min_term_overlap: int,
) -> EvidenceDecision:
    """Filter retrieved chunks to those usable as grounded evidence.

    Chunks below the effective relevance threshold, or without lexical overlap
    with the question, are discarded and never sent to the LLM.
    """
    max_score = max((item.score for item in scored), default=0.0)
    terms = question_terms(question)
    supporting: list[ScoredChunk] = []
    for item in scored:
        overlap = chunk_term_overlap_count(item.chunk.content, terms)
        if min_term_overlap > 0 and terms and overlap < min_term_overlap:
            continue
        if effective_relevance(item.score, overlap) < min_score:
            continue
        supporting.append(item)

    if not scored:
        return EvidenceDecision(
            supporting=[],
            insufficient=True,
            max_score=0.0,
            chunks_retrieved=0,
            reason="no_chunks_retrieved",
        )
    if not supporting:
        reason = (
            "max_relevance_below_threshold"
            if max_score < min_score
            else "insufficient_supporting_chunks"
        )
        return EvidenceDecision(
            supporting=[],
            insufficient=True,
            max_score=max_score,
            chunks_retrieved=len(scored),
            reason=reason,
        )
    if len(supporting) < min_supporting_chunks:
        return EvidenceDecision(
            supporting=[],
            insufficient=True,
            max_score=max_score,
            chunks_retrieved=len(scored),
            reason="insufficient_supporting_chunks",
        )
    return EvidenceDecision(
        supporting=supporting,
        insufficient=False,
        max_score=max_score,
        chunks_retrieved=len(scored),
        reason="ok",
    )


def suggestion_for_question(question: str) -> str | None:
    """Optional upload hint when evidence is insufficient."""
    terms = {term.lower() for term in re.findall(r"[A-Za-z]{3,}", question)}
    if terms & {"phishing", "malware", "cybersecurity", "security", "password"}:
        return "Try uploading an IT security or cybersecurity policy."
    if terms & {"pto", "vacation", "leave", "holiday"}:
        return "Try uploading an HR PTO or leave policy."
    if terms & {"expense", "reimbursement", "meal", "travel"}:
        return "Try uploading a finance or expense policy."
    if terms & {"parking"}:
        return "Try uploading a facilities or parking policy, if one exists."
    return "Try uploading a relevant policy document or refining your question."
