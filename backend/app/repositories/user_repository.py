"""User persistence operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    """Data-access helpers for the users table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        statement = select(User).where(User.email == normalized)
        return self._db.scalar(statement)

    def create(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str,
        role: UserRole = UserRole.EMPLOYEE,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name.strip(),
            role=role,
            is_active=is_active,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
