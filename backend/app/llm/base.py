"""LLM provider protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str
    latency_ms: int


class LLMProvider(Protocol):
    """Chat-completion style language model interface."""

    @property
    def model_name(self) -> str: ...

    def complete(self, messages: list[LLMMessage]) -> LLMResponse: ...
