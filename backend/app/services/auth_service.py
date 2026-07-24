"""Authentication use cases."""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token


class AuthService:
    """Registration, login, and token issuance."""

    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def register(self, payload: UserCreate) -> TokenResponse:
        """Register a new employee account and return an access token."""
        existing = self._users.get_by_email(payload.email)
        if existing is not None:
            raise AppError(
                "An account with this email already exists",
                status_code=409,
                code="email_taken",
            )

        user = self._users.create(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
            role=UserRole.EMPLOYEE,
        )
        return self._issue_token(user)

    def login(self, payload: UserLogin) -> TokenResponse:
        """Authenticate with email/password and return an access token."""
        user = self._users.get_by_email(payload.email)
        # One response for unknown, wrong password, and inactive accounts so
        # callers cannot probe whether an email is registered.
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AppError(
                "Invalid email or password",
                status_code=401,
                code="invalid_credentials",
            )
        if not user.is_active:
            raise AppError(
                "Invalid email or password",
                status_code=401,
                code="invalid_credentials",
            )
        return self._issue_token(user)

    def get_profile(self, user: User) -> UserResponse:
        """Return the public profile for the current user."""
        return UserResponse.model_validate(user)

    def _issue_token(self, user: User) -> TokenResponse:
        token, _expires_at = create_access_token(
            subject=user.id,
            role=user.role,
            settings=self._settings,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=self._settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
