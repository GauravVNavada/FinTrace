# FinTrace API

FastAPI service boundary for FinTrace. Deterministic financial rules remain in application services; PostgreSQL is an explicit repository implementation and application startup never runs migrations. The current API exposes the seeded MVP; the active evolution adds a separate FinancialInvestigation ingestion boundary without replacing canonical reconciliation.

## Current routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/health` | Process health only |
| GET | `/api/v1/dashboard/summary` | Demo aggregate, requires organization context |
| GET | `/api/v1/exceptions` | Demo exception list with enum filters |
| GET | `/api/v1/lifecycles/{order_id}` | Organization-scoped canonical lifecycle |
| POST | `/api/v1/exceptions/{exception_id}/investigations` | Bounded evidence investigation; requires tenant context and idempotency key |
| GET | `/api/v1/investigations/{investigation_id}` | Retrieve an investigation result |
| GET | `/api/v1/investigations/{investigation_id}/tool-calls` | Retrieve bounded tool-call evidence |
| POST | `/api/v1/exceptions/{exception_id}/resolution-request` | Create an idempotent simulated approval request |
| POST | `/api/v1/financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/resolution-request` | Create an idempotent approval request for an uploaded exception result |
| POST | `/api/v1/approvals/{request_id}/approve` | Apply one capability-authorized simulated approval |
| POST | `/api/v1/approvals/{request_id}/reject` | Apply one capability-authorized simulated rejection |
| GET | `/api/v1/audit-events` | Organization-scoped audit read for authorized roles |

## Evolution routes

The following Sprint 1 resource family is implemented with migration 005, API tests, and a live HTTP smoke path:

```text
POST /api/v1/financial-investigations
GET  /api/v1/financial-investigations
GET  /api/v1/financial-investigations/{id}
POST /api/v1/financial-investigations/{id}/sources
GET  /api/v1/financial-investigations/{id}/sources
DELETE /api/v1/financial-investigations/{id}/sources/{source_id}
```

The active Sprint 2 source-analysis contract is implemented with migration 006:

```text
POST  /api/v1/financial-investigations/{id}/sources/{source_id}/analyze
GET   /api/v1/financial-investigations/{id}/sources/{source_id}/analysis
GET   /api/v1/financial-investigations/{id}/sources/{source_id}/mappings
PATCH /api/v1/financial-investigations/{id}/sources/{source_id}/mappings/{mapping_id}
POST  /api/v1/financial-investigations/{id}/sources/{source_id}/mappings/confirm
PATCH /api/v1/financial-investigations/{id}/sources/{source_id}/classification
```

The default `stub` provider is explicitly offline/deterministic. A configured OpenAI-compatible provider receives bounded metadata and samples only, selects from the server allowlist of read-only tools, and has its output validated; it cannot normalize records or mutate financial state. `gemini`, `google`, and `groq` are supported aliases for this adapter. Staging and production settings reject the offline provider and require `AI_API_KEY`. For local convenience, `apps/api/.env` contains two Gemini and two Groq key slots; the first non-empty slot for the selected provider is used when `AI_API_KEY` is blank, and requests retry remaining keys after rate-limit, transient, or authentication failures. Set `AI_FALLBACK_PROVIDER` to explicitly fail over to the other provider after the primary provider is exhausted. Automated tests force the deterministic stub and do not consume live quota.

## Run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8001
```

Development requests may use `X-Organization-Id`, `X-Actor-Id`, and `X-Actor-Role` only while `AUTH_MODE=development`. Bearer tokens with verified HS256 claims are supported; set `AUTH_MODE=required` before deployment to reject header-only context.

## Design rules

- Routes depend on typed schemas and application repositories.
- Repositories require organization scope.
- Demo repository is deterministic and process-local; PostgreSQL is the durable runtime.
- No route accepts organization scope from a request body.
- Migrations 004–006 persist investigation/evaluation/control workflow snapshots, idempotency responses, ordered tool calls, FinancialInvestigation workspaces, source metadata, source analyses, and mapping proposals. Audit events remain append-only. The default stub provider is safe for local development and does not call an external service.
