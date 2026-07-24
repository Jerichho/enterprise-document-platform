"""Sanitize assistant answer text so retrieval metadata never leaks."""

from __future__ import annotations

import re

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_META_FIELD_RE = re.compile(
    r"\b(?:title|department|chunk_id|relevance_score|page_number)\s*=\s*"
    r"(?:'[^']*'|\"[^\"]*\"|[^\s;]+)",
    re.IGNORECASE,
)
_SCORE_RE = re.compile(r"\bscore\s*=\s*[0-9]*\.?[0-9]+", re.IGNORECASE)
_SOURCE_MARK_RE = re.compile(r"\(\s*see\s+Source\s+\d+\s*\)", re.IGNORECASE)
_SOURCE_TAG_RE = re.compile(r"\[Source\s+\d+\]", re.IGNORECASE)
_BASED_ON_RE = re.compile(
    r"^\s*Based on the provided documents:\s*",
    re.IGNORECASE,
)


def sanitize_answer_text(text: str) -> str:
    """Strip prompt/metadata leakage from model output."""
    cleaned = text.strip()
    cleaned = _BASED_ON_RE.sub("", cleaned)
    cleaned = _SOURCE_MARK_RE.sub("", cleaned)
    cleaned = _SOURCE_TAG_RE.sub("", cleaned)
    cleaned = _META_FIELD_RE.sub("", cleaned)
    cleaned = _SCORE_RE.sub("", cleaned)
    cleaned = _UUID_RE.sub("", cleaned)
    cleaned = re.sub(r"[;,]{2,}", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    return cleaned.strip(" ;,\n\t")
