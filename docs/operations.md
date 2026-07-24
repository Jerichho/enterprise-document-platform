# Operations

## Health probes

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness — process is up (`status`, `service`, `version`, `environment`) |
| `GET /ready` | Readiness — dependency checks with overall `ready` / `degraded` / `not_ready` |

### Required vs optional

| Check | Severity |
|-------|----------|
| `database` | Required — unavailable → HTTP **503** `not_ready` |
| `pgvector` | Required — unavailable → **503** `not_ready` |
| `storage` | Required — unavailable → **503** `not_ready` |
| `llm_provider` | Optional — misconfigured → HTTP **200** `degraded` |
| `embedding_provider` | Optional — misconfigured → HTTP **200** `degraded` |

`degraded` means core traffic can continue; RAG/chat may fail until providers are fixed.
Probe responses never include secret values.

The Status page (`/status`) polls these endpoints and can auto-refresh every 15s.

## Migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

## Logging

Set `LOG_FORMAT=json` (default) or `text`. JSON logs include `timestamp`, `level`,
`logger`, `message`, `request_id`, and request fields (`method`, `path`, `status_code`,
`duration_ms`) when present. Sensitive substrings (API keys, bearer tokens, passwords)
are redacted.

Every response includes:

- `X-Request-ID` — correlation ID (echoed from the client or generated)
- `X-Response-Time-Ms` — handler duration

Error responses also include `request_id` in the JSON body.

## Ingestion duration

Completed and failed ingestion jobs store `duration_ms` (started → finished) for
admin analytics and ops debugging.

## Background jobs

Ingestion uses **FastAPI BackgroundTasks** in the API process (not a separate worker pool).

Implications:

- Jobs are durable in Postgres (`ingestion_jobs`) with stage updates on the document
- Killing or redeploying the API can leave `pending`/`running` rows orphaned
- On startup the app fails jobs older than `INGESTION_STALE_JOB_MINUTES` (default 30)
- Admins can also call `POST /api/v1/admin/ingestion-jobs/recover-stale`
- After recovery, use document **Reprocess** to enqueue a new attempt

Horizontal scale requires an external queue (Celery/RQ/ARQ) sharing the same job table;
BackgroundTasks alone does not distribute work across multiple API replicas.

## Docker

```bash
docker compose up --build
```

API runs migrations on startup. Images are also built in CI without deploying.

## Azure readiness

See [azure.md](azure.md) for the full deployment plan. Short checklist:

- 12-factor config via environment variables
- Stateless API containers + managed PostgreSQL with pgvector
- Swap `STORAGE_BACKEND` to Azure Blob when the adapter is implemented
- Use Azure Key Vault / Container Apps secrets for `SECRET_KEY` and API keys
- Map `/health` and `/ready` to platform probes (`degraded` still returns 200)
