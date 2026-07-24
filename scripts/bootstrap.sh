#!/usr/bin/env bash
# Bootstrap local development: copy env files and print next steps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT/backend/.env" ]]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  echo "Created backend/.env from .env.example"
else
  echo "backend/.env already exists"
fi

if [[ ! -f "$ROOT/frontend/.env" ]]; then
  cp "$ROOT/frontend/.env.example" "$ROOT/frontend/.env"
  echo "Created frontend/.env from .env.example"
else
  echo "frontend/.env already exists"
fi

echo
echo "Next steps:"
echo "  1. docker compose up -d db"
echo "  2. cd backend && python -m venv .venv && source .venv/bin/activate"
echo "  3. pip install -e '.[dev]' && alembic upgrade head"
echo "  4. uvicorn app.main:app --reload --port 8000"
echo "  5. cd frontend && npm install && npm run dev"
echo "  6. make seed   # admin@example.com / admin123"
