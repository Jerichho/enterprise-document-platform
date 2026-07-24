"""Deterministic fake embeddings for tests and local development."""

from __future__ import annotations

import hashlib
import math
import re

# Down-weight ubiquitous English/policy words so distinctive terms dominate.
_COMMON = frozenset(
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
        "must",
        "may",
        "will",
        "shall",
        "section",
        "date",
        "effective",
        "department",
    }
)


class FakeEmbeddingProvider:
    """Token-hashed embeddings that never call external APIs.

    Longer / rarer tokens receive higher weight so queries about distinct topics
    (e.g. phishing vs PTO) separate more clearly than a uniform bag-of-tokens.
    """

    def __init__(self, dimensions: int = 768) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self._dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            values[0] = 1.0
            return _l2_normalize(values)

        for token in tokens:
            weight = self._token_weight(token)
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset, byte in enumerate(digest):
                index = (byte + offset * 31) % self._dimensions
                values[index] += weight
            # Character trigrams add discrimination for distinctive words.
            if len(token) >= 5 and token not in _COMMON:
                for i in range(len(token) - 2):
                    tri = token[i : i + 3]
                    digest = hashlib.sha256(f"tri:{tri}".encode()).digest()
                    index = digest[0] % self._dimensions
                    values[index] += weight * 0.35
        return _l2_normalize(values)

    @staticmethod
    def _token_weight(token: str) -> float:
        if token in _COMMON:
            return 0.12
        # Longer tokens (phishing, reimbursement, forklift) dominate.
        return 1.0 + min(len(token), 16) / 3.0


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]
