"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.llm.base import LLMProvider
from app.llm.fake import FakeLLMProvider
from app.llm.together import TogetherLLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Create the configured LLM backend."""
    if settings.llm_provider == "fake" or settings.app_env == "test":
        return FakeLLMProvider(model_name=settings.together_model)
    if settings.llm_provider == "together":
        return TogetherLLMProvider(settings)
    raise AppError(
        f"Unknown LLM provider '{settings.llm_provider}'",
        status_code=500,
        code="invalid_llm_provider",
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())
