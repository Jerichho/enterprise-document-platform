"""System health and readiness response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness response for container orchestrators."""

    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class DependencyStatus(BaseModel):
    """Status of a single runtime dependency."""

    name: str
    status: Literal["ok", "degraded", "unavailable"]
    detail: str | None = None


class ReadyResponse(BaseModel):
    """Readiness response including dependency checks."""

    status: Literal["ready", "degraded", "not_ready"]
    environment: str
    version: str
    checks: list[DependencyStatus] = Field(default_factory=list)
    demo_mode: bool = False
    llm_provider: str | None = None
    embedding_provider: str | None = None
