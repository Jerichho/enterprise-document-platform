"""FastAPI security dependencies for authentication and RBAC."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import write_audit
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.database.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.security.tokens import TokenError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    """Provide a UserRepository bound to the request session."""
    return UserRepository(db)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Resolve the authenticated user from a Bearer access token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            "Not authenticated",
            status_code=401,
            code="not_authenticated",
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = UUID(str(payload["sub"]))
    except (TokenError, ValueError) as exc:
        raise AppError(
            "Invalid or expired access token",
            status_code=401,
            code="invalid_token",
        ) from exc

    user = users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise AppError(
            "User not found or inactive",
            status_code=401,
            code="invalid_token",
        )
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    """Dependency factory that enforces one of the allowed roles."""

    def _dependency(
        request: Request,
        db: Annotated[Session, Depends(get_db)],
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            write_audit(
                db,
                request,
                action="auth.access_denied",
                actor_user_id=current_user.id,
                resource_type="route",
                resource_id=request.url.path,
                success=False,
                details={
                    "required_roles": [role.value for role in allowed_roles],
                    "actual_role": current_user.role.value,
                },
                error_message="Insufficient permissions",
            )
            raise AppError(
                "Insufficient permissions",
                status_code=403,
                code="forbidden",
            )
        return current_user

    return _dependency


RequireAdmin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
RequireEmployeeOrAdmin = Annotated[
    User,
    Depends(require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)),
]
CurrentUser = Annotated[User, Depends(get_current_user)]
