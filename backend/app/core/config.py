"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the API and infrastructure integrations."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Enterprise Knowledge Management Platform"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    secret_key: str = Field(
        default="change-me-to-a-long-random-string-in-production",
        min_length=16,
    )

    # Database
    database_url: str = "postgresql+psycopg://ekp:ekp_secret@localhost:5432/ekp"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Auth (Phase 2+)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Rate limiting (Phase 7)
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 120
    rate_limit_auth_per_minute: int = 20
    rate_limit_upload_per_minute: int = 30
    rate_limit_chat_per_minute: int = 40

    # Storage
    storage_backend: Literal["local", "azure"] = "local"
    storage_local_path: str = "./storage/uploads"
    upload_max_size_mb: int = 25
    # Azure Blob (used when STORAGE_BACKEND=azure). Prefer Key Vault in production.
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "documents"
    # Optional: documented for App Insights / OpenTelemetry agents (stdout JSON is primary).
    applicationinsights_connection_string: str = ""

    # Embeddings — default fake so local boot works without API keys.
    # Set EMBEDDING_PROVIDER=together + TOGETHER_API_KEY for real RAG.
    embedding_provider: Literal["together", "fake"] = "fake"
    embedding_model: str = "togethercomputer/m2-bert-80M-8k-retrieval"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 32

    # LLM — default fake; set LLM_PROVIDER=together for real completions.
    llm_provider: Literal["together", "fake"] = "fake"
    together_api_key: str = ""
    together_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    together_base_url: str = "https://api.together.xyz/v1"
    llm_request_timeout_seconds: int = 60
    llm_max_retries: int = 3

    # RAG — similarity score ranges differ by embedding model; calibrate in each env.
    # Defaults favor refusal over weakly related "grounded" answers for fake embeddings.
    rag_top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        validation_alias=AliasChoices("RAG_TOP_K", "RETRIEVAL_TOP_K"),
    )
    rag_min_relevance_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("RAG_MIN_RELEVANCE_SCORE", "RETRIEVAL_MIN_SCORE"),
    )
    rag_min_supporting_chunks: int = Field(default=1, ge=1, le=20)
    rag_min_term_overlap: int = Field(
        default=1,
        ge=0,
        le=10,
        description="Minimum question terms that must appear in a supporting chunk",
    )
    rag_answer_style: Literal["concise", "detailed"] = "concise"
    chunk_size: int = 800
    chunk_overlap: int = 150

    @property
    def retrieval_top_k(self) -> int:
        """Backward-compatible alias for rag_top_k."""
        return self.rag_top_k

    @property
    def retrieval_min_score(self) -> float:
        """Backward-compatible alias for rag_min_relevance_score."""
        return self.rag_min_relevance_score

    # Ingestion jobs (BackgroundTasks)
    # Jobs stuck in pending/running longer than this are marked failed on startup/recover.
    ingestion_stale_job_minutes: int = 30

    @field_validator("cors_origins", mode="before")
    @classmethod
    def normalize_cors_origins(cls, value: object) -> object:
        """Allow JSON-style lists in env while storing a comma-separated string."""
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Parsed CORS origins for FastAPI middleware."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def assert_secure_for_environment(self) -> None:
        """Refuse insecure defaults when running in production."""
        if not self.is_production:
            return
        insecure_markers = (
            "change-me-to-a-long-random-string-in-production",
            "change-me",
            "test-secret-key",
        )
        secret = self.secret_key.strip().lower()
        if any(marker in secret for marker in insecure_markers) or len(self.secret_key) < 32:
            raise RuntimeError(
                "Refusing to start in production with an insecure SECRET_KEY. "
                "Set a unique SECRET_KEY of at least 32 characters."
            )
        if "ekp_secret" in self.database_url:
            raise RuntimeError(
                "Refusing to start in production with the default database password. "
                "Set DATABASE_URL to a strong credential."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
