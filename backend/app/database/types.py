"""SQLAlchemy type that uses pgvector on PostgreSQL and JSON on SQLite."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator, UserDefinedType


class _PGVector(UserDefinedType[list[float]]):
    """Thin wrapper so Alembic/SQLAlchemy can emit VECTOR(n) on PostgreSQL."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kwargs: Any) -> str:
        return f"VECTOR({self.dimensions})"

    def bind_processor(self, _dialect: Dialect) -> Any:
        def process(value: list[float] | None) -> list[float] | None:
            return value

        return process

    def result_processor(self, _dialect: Dialect, _coltype: Any) -> Any:
        def process(value: Any) -> list[float] | None:
            if value is None:
                return None
            return list(value)

        return process


class EmbeddingVector(TypeDecorator[list[float]]):
    """Store float embeddings as pgvector on Postgres and JSON text on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 768) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dimensions))
            except ImportError:
                return dialect.type_descriptor(_PGVector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(
        self,
        value: list[float] | None,
        dialect: Dialect,
    ) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(
        self,
        value: Any,
        dialect: Dialect,
    ) -> list[float] | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return list(value)
        if isinstance(value, str):
            loaded = json.loads(value)
            return [float(item) for item in loaded]
        return list(value)
