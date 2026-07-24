"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure tests use a predictable environment before the app imports settings.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-16-chars")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")
os.environ.setdefault("RETRIEVAL_MIN_SCORE", "0.15")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://ekp:ekp_secret@localhost:5432/ekp",
)

from app.core.config import get_settings
from app.database.session import Base, get_db
from app.ingestion.embeddings import get_embedding_provider
from app.llm.factory import get_llm_provider
from app.main import create_app
from app.models import (  # noqa: F401
    AuditLog,
    Citation,
    Conversation,
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
    Message,
    User,
)
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.storage.factory import get_storage_service
from app.storage.local import LocalStorageService


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Reset cached settings between tests when env vars change."""
    get_settings.cache_clear()
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()
    yield
    get_settings.cache_clear()
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Isolated in-memory SQLite session shared via StaticPool."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def storage(tmp_path) -> LocalStorageService:
    """Isolated local storage root for each test."""
    return LocalStorageService(tmp_path / "uploads")


@pytest.fixture
def client(
    db_session: Session,
    storage: LocalStorageService,
) -> Generator[TestClient, None, None]:
    """HTTP test client with DB and storage dependencies overridden."""
    app = create_app()
    get_settings.cache_clear()
    get_storage_service.cache_clear()
    get_embedding_provider.cache_clear()
    get_llm_provider.cache_clear()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_storage() -> LocalStorageService:
        return storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_storage_service.cache_clear()


@pytest.fixture
def user_repo(db_session: Session) -> UserRepository:
    return UserRepository(db_session)


def _create_user(
    repo: UserRepository,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
) -> User:
    return repo.create(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
        is_active=is_active,
    )


@pytest.fixture
def employee_user(user_repo: UserRepository) -> User:
    return _create_user(
        user_repo,
        email="employee@example.com",
        password="password123",
        full_name="Example Employee",
        role=UserRole.EMPLOYEE,
    )


@pytest.fixture
def admin_user(user_repo: UserRepository) -> User:
    return _create_user(
        user_repo,
        email="admin@example.com",
        password="password123",
        full_name="Example Admin",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def employee_token(employee_user: User) -> str:
    token, _ = create_access_token(
        subject=employee_user.id,
        role=employee_user.role,
        settings=get_settings(),
    )
    return token


@pytest.fixture
def admin_token(admin_user: User) -> str:
    token, _ = create_access_token(
        subject=admin_user.id,
        role=admin_user.role,
        settings=get_settings(),
    )
    return token
