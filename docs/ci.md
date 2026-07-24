# Continuous integration

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

## Gates

1. **Backend** (Ubuntu + `pgvector/pgvector:pg16` service)
   - `pip install -e ".[dev]"`
   - Ruff lint
   - Ruff format `--check`
   - MyPy (`app`)
   - Alembic: exactly one head, `upgrade head`, `current`
   - Pytest
2. **Frontend**
   - `npm ci`
   - ESLint (`--max-warnings 0`)
   - `tsc --noEmit`
   - Vitest
   - `npm run build`
3. **Docker** (after 1–2 succeed)
   - `docker build` for `backend/` and `frontend/` (`--target production`)

Jobs fail the workflow on the first failing step. Concurrency cancels superseded runs on the
same branch.

## Local parity

```bash
make check
```
