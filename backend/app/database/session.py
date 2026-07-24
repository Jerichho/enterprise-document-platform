"""Database engine, session management, and declarative base."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def create_db_engine(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine from application settings or an explicit URL."""
    database_url = url or get_settings().database_url
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10

    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return True when the database accepts a simple query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_pgvector_extension() -> tuple[bool, str | None]:
    """Return whether the pgvector extension is available when using PostgreSQL."""
    database_url = get_settings().database_url
    if database_url.startswith("sqlite"):
        return True, "SQLite test dialect (pgvector not required)"
    try:
        with engine.connect() as connection:
            installed = connection.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
        if installed:
            return True, "vector extension installed"
        return False, "pgvector extension is not installed"
    except Exception:
        return False, "Unable to verify pgvector extension"
