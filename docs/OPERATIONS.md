# Operations & Observability

Reference for the platform features added in the Month 1 hardening pass
(security, caching, observability). For setup see the [README](../README.md).

## Authentication

Two mechanisms, both resolved to a `User`:

| Method | Header | Use case |
|--------|--------|----------|
| JWT bearer | `Authorization: Bearer <jwt>` | Browser / SPA sessions |
| API key | `X-API-Key: dpk_...` | Scripts, MCP, CI |

API keys are created via `POST /api/v1/api-keys` and returned **once** in
plaintext. Only a hash (plus a 12-char prefix for lookup) is stored. Revoke
with `DELETE /api/v1/api-keys/{id}`.

### Roles (RBAC)

Roles are ordered: `viewer < user < admin`. Protect a route with
`require_role(UserRole.ADMIN)`. Non-admins are scoped to their own documents
in list/search endpoints. The legacy `is_admin` flag is still honored as a
fallback.

## Caching

| Cache | Backend | TTL env | Default |
|-------|---------|---------|---------|
| Embeddings | Redis | — | 24h |
| Search results | Redis | `CACHE_TTL_SEARCH` | 300s |
| RAG answers | Redis | `CACHE_TTL_RAG` | 600s |

- Falls back to a no-op (cache miss) if Redis is unavailable — the app keeps working.
- Deleting a document invalidates the `search` and `rag` namespaces.
- Inspect: `GET /api/v1/admin/cache/stats` → `{hits, misses, errors, hit_rate}`.
- Clear: `POST /api/v1/admin/cache/invalidate?namespace=search`.

## Search

- **Semantic** (`POST /api/v1/search`): vector search over Qdrant with MMR rerank.
- **Keyword** (`GET /api/v1/search/keyword?q=...`): Postgres full-text search
  (`plainto_tsquery` + `ts_rank`) backed by the `idx_doc_fts` GIN index.

## Observability

### Metrics
Prometheus metrics at `GET /metrics` (request counts, latency histograms,
process metrics) via `prometheus-fastapi-instrumentator`. Point a Prometheus
scrape at this endpoint; build Grafana panels on `http_request_duration_seconds`.

### Health probes
| Endpoint | Purpose | Failure behavior |
|----------|---------|------------------|
| `GET /api/v1/health/live` | Liveness — process up | k8s restarts pod |
| `GET /api/v1/health/ready` | Readiness — deps OK | 503 if DB down → k8s stops routing |
| `GET /api/v1/health` | Human-readable DB status | — |

Readiness checks DB (required), Redis and Qdrant (degrade gracefully).

### Logging
Structured JSON logs (structlog) to stdout with a per-request `request_id`
correlation ID. Level defaults to `DEBUG` in development and `INFO` in
production (override with `LOG_LEVEL`). **Log rotation** is intentionally the
orchestrator's job — Docker/journald/k8s rotate stdout; the app does not write
log files.

## Security headers & CORS
Every response carries `X-Content-Type-Options`, `X-Frame-Options: DENY`,
`Referrer-Policy`, `Permissions-Policy`, plus `Strict-Transport-Security` in
production. CORS origins are whitelisted via `CORS_ORIGINS` (comma-separated).

## Load testing
```bash
pip install locust
API_KEY=dpk_xxx locust -f tests/load/locustfile.py --host http://localhost:8000
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `could not translate host name "db"` on migrate | Running Alembic on host with Docker `.env` | Start Postgres (`docker compose up -d db`) or point `DATABASE_URL` at `localhost:5433` |
| `/metrics` returns 404 | instrumentator not installed | `pip install prometheus-fastapi-instrumentator` |
| Search returns stale results after delete | Redis cache | Auto-invalidated on delete; else `POST /admin/cache/invalidate` |
| `cache_stats` always 0 hits | Redis unavailable | Check `REDIS_URL`; cache degrades to no-op |
| Keyword search empty but docs exist | FTS migration not applied | `alembic upgrade head` (adds `idx_doc_fts`) |
