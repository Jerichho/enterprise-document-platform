# Technical decisions (interview notes)

Short rationale for the choices that usually come up in portfolio reviews.

## Why FastAPI + SQLAlchemy + React?

Clear separation of API contracts (Pydantic), persistence (repositories), and use cases
(services). The React SPA stays a thin client over JWT-authenticated HTTP.

## Why pgvector in Postgres instead of a separate vector DB?

One operational database for metadata, ACLs-related ownership, audit logs, and embeddings.
HNSW cosine search (`<=>`) is enough for portfolio-scale corpora and keeps local setup
simple. A dedicated vector store would be justified for multi-tenant isolation or
massive corpora.

## Why fake providers by default?

Local boot and CI must not require paid API keys. `EMBEDDING_PROVIDER=fake` and
`LLM_PROVIDER=fake` implement the same interfaces as Together.ai so tests exercise the
real orchestration path. Flip env vars for live demos.

## Why FastAPI BackgroundTasks for ingestion?

Upload returns immediately with a durable `IngestionJob`. BackgroundTasks is the lightest
async option for a single API process. Atomic job claim + stale recovery cover crash
orphans. Production scale-out keeps the same job table and moves workers to Celery/RQ/ARQ.

## Why refuse answers below `RETRIEVAL_MIN_SCORE`?

Grounding without a threshold still hallucinates. The assistant returns an explicit
insufficient-context refusal and empty citations when retrieval is weak—honest UX for
enterprise demos.

## Why bcrypt JWT without refresh tokens?

Adequate for a portfolio SPA with short-lived access tokens. Refresh flows, SSO, and
session revocation belong in a production identity layer (Entra ID / Auth0).

## Why layering (API → service → repository)?

Route handlers stay thin: validate, authorize, call a service, write audit. Business
rules and provider orchestration live in services so they can be unit-tested without HTTP.

## Known limitations (honest)

- Ingestion runs in-process (not horizontally scaled).
- Rate limiting is in-memory (not multi-instance safe).
- Azure Blob is optional behind the same storage protocol; local filesystem is the default.
- Conversations are user-scoped; documents are org-wide (no per-doc ACL matrix).
- Grounding reduces unsupported answers; it does not eliminate LLM hallucinations.
