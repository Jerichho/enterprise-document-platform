# Security notes

## Secrets

- Never commit `.env` files or API keys.
- Configure `SECRET_KEY`, `TOGETHER_API_KEY`, and database credentials via environment
  variables or a secret manager (Azure Key Vault in cloud deployments).
- `SECRET_KEY` must be a long random value in production (minimum 16 characters enforced).

## Authentication and authorization

- Passwords are hashed with bcrypt.
- JWT access tokens use HS256 and expire according to `ACCESS_TOKEN_EXPIRE_MINUTES`
  (default 60). Refresh tokens are intentionally omitted for this portfolio SPA;
  clients re-authenticate after expiry.
- Login failures always return the same `401 invalid_credentials` response so
  callers cannot probe whether an email exists (including inactive accounts).
- Admin-only routes: document upload/delete/reprocess and `/api/v1/admin/*`.
- Conversations are scoped to the owning user (admins may view all).
- Production startup refuses insecure default `SECRET_KEY` values and the compose
  default database password (`ekp_secret`).
- `scripts/create_admin.sh` only runs when `APP_ENV` is `development` or `test`
  unless `--force` is passed.

## Upload security

- Allowed types: PDF, DOCX, TXT.
- Size limited by `UPLOAD_MAX_SIZE_MB`.
- Extension, content-type, and magic-byte checks in `file_validation.py`.
- Local storage rejects path traversal (`..`) in object keys.

## Rate limiting

In-process sliding-window limits (single instance):

| Group | Default / minute | Env var |
|-------|------------------|---------|
| auth | 20 | `RATE_LIMIT_AUTH_PER_MINUTE` |
| documents | 30 | `RATE_LIMIT_UPLOAD_PER_MINUTE` |
| chat | 40 | `RATE_LIMIT_CHAT_PER_MINUTE` |
| default | 120 | `RATE_LIMIT_DEFAULT_PER_MINUTE` |

Disable with `RATE_LIMIT_ENABLED=false`. For multi-instance production, replace the
middleware store with Redis (or API gateway limits) using the same grouping.

## Audit logging

Security-relevant actions are written to `audit_logs`:

- `auth.login` / `auth.register` (success and failure)
- `document.upload` / `document.delete` / `document.reprocess`
- `auth.access_denied` when an authenticated user hits a forbidden role gate

Admins can review them via `GET /api/v1/admin/audit-logs`.

## CORS

Configure allowed browser origins with `CORS_ORIGINS` (comma-separated).
