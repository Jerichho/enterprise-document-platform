#!/usr/bin/env bash
# Seed local development users (idempotent).
# Creates a default admin and employee when they do not already exist.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"
ADMIN_NAME="${ADMIN_NAME:-Platform Admin}"
EMPLOYEE_EMAIL="${EMPLOYEE_EMAIL:-employee@example.com}"
EMPLOYEE_PASSWORD="${EMPLOYEE_PASSWORD:-employee123}"
EMPLOYEE_NAME="${EMPLOYEE_NAME:-Example Employee}"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ -z "${APP_ENV:-}" && -f .env ]]; then
  APP_ENV="$(grep -E '^APP_ENV=' .env | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi
APP_ENV="${APP_ENV:-development}"
if [[ "$APP_ENV" != "development" && "$APP_ENV" != "test" ]]; then
  echo "Refusing to seed users when APP_ENV=${APP_ENV} (use development/test)."
  exit 1
fi

ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" ADMIN_NAME="$ADMIN_NAME" \
EMPLOYEE_EMAIL="$EMPLOYEE_EMAIL" EMPLOYEE_PASSWORD="$EMPLOYEE_PASSWORD" EMPLOYEE_NAME="$EMPLOYEE_NAME" \
python - <<'PY'
from __future__ import annotations

import os

from app.database.session import SessionLocal
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.security.passwords import hash_password


def upsert(
    repo: UserRepository,
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole,
) -> str:
    existing = repo.get_by_email(email)
    if existing is not None:
        return f"exists  {email} ({existing.role.value})"
    user = repo.create(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    return f"created {user.email} ({user.role.value})"


db = SessionLocal()
try:
    repo = UserRepository(db)
    print(
        upsert(
            repo,
            email=os.environ["ADMIN_EMAIL"],
            password=os.environ["ADMIN_PASSWORD"],
            full_name=os.environ["ADMIN_NAME"],
            role=UserRole.ADMIN,
        )
    )
    print(
        upsert(
            repo,
            email=os.environ["EMPLOYEE_EMAIL"],
            password=os.environ["EMPLOYEE_PASSWORD"],
            full_name=os.environ["EMPLOYEE_NAME"],
            role=UserRole.EMPLOYEE,
        )
    )
finally:
    db.close()
PY

echo
echo "Default local credentials (change in shared environments):"
echo "  admin    ${ADMIN_EMAIL} / ${ADMIN_PASSWORD}"
echo "  employee ${EMPLOYEE_EMAIL} / ${EMPLOYEE_PASSWORD}"
