.PHONY: lint check format test migrate run coverage seed

lint:
	cd backend && .venv/bin/ruff check app tests --fix
	cd backend && .venv/bin/mypy app
	cd frontend && npm run lint

check:
	cd backend && .venv/bin/ruff check app tests
	cd backend && .venv/bin/ruff format --check app tests
	cd backend && .venv/bin/mypy app
	cd backend && .venv/bin/pytest -q
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test
	cd frontend && npm run build

format:
	cd backend && .venv/bin/ruff format app tests
	cd backend && .venv/bin/ruff check app tests --fix

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

coverage:
	cd backend && .venv/bin/pytest -q --cov=app --cov-report=term-missing:skip-covered --cov-report=html:htmlcov
	cd frontend && npm run test:coverage

migrate:
	cd backend && .venv/bin/alembic upgrade head

run:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

seed:
	bash scripts/seed_dev.sh
