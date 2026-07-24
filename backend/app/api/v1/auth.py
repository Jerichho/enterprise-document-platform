"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import write_audit
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.database.session import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.security.dependencies import CurrentUser
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    """Wire AuthService with request-scoped dependencies."""
    return AuthService(UserRepository(db), settings)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: Request,
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Create an employee account and return a JWT access token."""
    try:
        result = auth.register(payload)
    except AppError as exc:
        write_audit(
            db,
            request,
            action="auth.register",
            success=False,
            details={"email": str(payload.email)},
            error_message=exc.message,
        )
        raise
    write_audit(
        db,
        request,
        action="auth.register",
        actor_user_id=result.user.id,
        resource_type="user",
        resource_id=result.user.id,
        details={"email": result.user.email},
    )
    return result


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    payload: UserLogin,
    db: Annotated[Session, Depends(get_db)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Authenticate an existing user and return a JWT access token."""
    try:
        result = auth.login(payload)
    except AppError as exc:
        write_audit(
            db,
            request,
            action="auth.login",
            success=False,
            details={"email": str(payload.email)},
            error_message=exc.message,
        )
        raise
    write_audit(
        db,
        request,
        action="auth.login",
        actor_user_id=result.user.id,
        resource_type="user",
        resource_id=result.user.id,
        details={"email": result.user.email},
    )
    return result


@router.get("/me", response_model=UserResponse)
def me(
    current_user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    """Return the authenticated user's profile."""
    return auth.get_profile(current_user)
