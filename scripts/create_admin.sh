#!/usr/bin/env bash
# Create an admin user (registration always creates employees).
# By default only allowed when APP_ENV is development or test.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

FORCE=0
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--force" ]]; then
    FORCE=1
  else
    ARGS+=("$arg")
  fi
done

EMAIL="${ARGS[0]:-}"
PASSWORD="${ARGS[1]:-}"
FULL_NAME="${ARGS[2]:-Platform Admin}"

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Usage: $0 <email> <password> [full_name] [--force]"
  exit 1
fi

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Load APP_ENV from backend/.env when present without overriding an explicit export.
if [[ -z "${APP_ENV:-}" && -f .env ]]; then
  APP_ENV="$(grep -E '^APP_ENV=' .env | head -n1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
fi

APP_ENV="${APP_ENV:-development}"
if [[ "$FORCE" -ne 1 && "$APP_ENV" != "development" && "$APP_ENV" != "test" ]]; then
  echo "Refusing to create an admin user when APP_ENV=${APP_ENV}."
  echo "Use development/test, or pass --force for an intentional production bootstrap."
  exit 1
fi

EMAIL="$EMAIL" PASSWORD="$PASSWORD" FULL_NAME="$FULL_NAME" python - <<'PY'
import os

from app.database.session import SessionLocal
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.security.passwords import hash_password

email = os.environ["EMAIL"]
password = os.environ["PASSWORD"]
full_name = os.environ["FULL_NAME"]

db = SessionLocal()
try:
    repo = UserRepository(db)
    existing = repo.get_by_email(email)
    if existing is not None:
        raise SystemExit(f"User already exists: {email}")
    user = repo.create(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=UserRole.ADMIN,
    )
    print(f"Created admin user {user.email} ({user.id})")
finally:
    db.close()
PY
