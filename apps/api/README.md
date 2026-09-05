# FinTrace API

FastAPI service boundary for FinTrace. Deterministic financial rules remain in application services; PostgreSQL is an explicit repository implementation and application startup never runs migrations. The current API exposes the seeded MVP; the active evolution adds a separate FinancialInvestigation ingestion boundary without replacing canonical reconciliation.

## Current routes

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/health` | Process health only |
| GET | `/api/v1/dashboard/summary` | Sample aggregate, requires organization context |
| GET | `/api/v1/exceptions` | Sample exception list with enum filters |
| GET | `/api/v1/lifecycles/{order_id}` | Organization-scoped canonical lifecycle |
| POST | `/api/v1/exceptions/{exception_id}/investigations` | Bounded evidence investigation; requires tenant context and idempotency key |
| GET | `/api/v1/investigations/{investigation_id}` | Retrieve an investigation result |
| GET | `/api/v1/investigations/{investigation_id}/tool-calls` | Retrieve bounded tool-call evidence |
| GET | `/api/v1/ai/provider-health` | Check configured provider credentials/model reachability with a minimal structured request |
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

The local sample uses Groq with model `openai/gpt-oss-120b` when `AI_PROVIDER=groq` and `GROQ_API_KEY` are configured. Gemini and other OpenAI-compatible providers remain supported by explicit configuration. A configured provider receives bounded metadata and samples only, selects from the server allowlist of read-only tools, and has its output validated; it cannot normalize records or mutate financial state. `GeminiProvider` reads `GEMINI_API_KEY` and `GroqProvider` reads `GROQ_API_KEY`; legacy numbered slots remain supported for existing local deployments. The runtime model and endpoint are configurable. Authentication, authorization, unsupported-model, and malformed-output failures are surfaced immediately; only bounded transient failures can trigger explicit fallback. Automated tests force the deterministic stub and do not consume live quota.

## Run

## P0 live-provider contract

Set `AI_PROVIDER=groq`, `AI_MODEL=openai/gpt-oss-120b`, and `GROQ_API_KEY` for the local live-sample path. Check `/api/v1/ai/provider-health` before starting a sample; it reports primary and fallback separately and caches the result briefly. Source analysis sends only the filename, headers, inferred types, row count, bounded sample rows, and basic statistics. Exception investigation receives deterministic findings and returned evidence, then chooses one allowlisted read-only tool per turn up to eight calls. Outputs are schema-validated and fact-verified. A provider outage returns an explicit `UNAVAILABLE` health result and persisted `FAILED` investigation with provider, model, error category, retryability, request stage, iteration, and latency; it never silently becomes stub output or `UNRESOLVED`, while deterministic reconciliation remains available. Live requests require explicit use of the live configuration; the AI benchmark is exposed separately at `/api/v1/evaluation/ai/run` and `/api/v1/evaluation/ai/latest`.

The explicit live smoke is `RUN_LIVE_AI_TESTS=1 python scripts/live_ai_smoke.py` from the repository root (on Windows, set `$env:RUN_LIVE_AI_TESTS="1"` first). It performs provider health, one source analysis, and one complete investigation; it never prints credentials. Normal pytest/CI paths force the stub and do not call live APIs.

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
- Sample repository is deterministic and process-local; PostgreSQL is the durable runtime.
- No route accepts organization scope from a request body.
- Migrations 004–013 persist investigation/evaluation/control workflow snapshots, idempotency responses, ordered tool calls, FinancialInvestigation workspaces, source metadata, source analyses, mapping proposals, immutable normalized datasets, reconciliation runs/results, uploaded investigations, approval requests, and live-provider diagnostics. Audit events remain append-only. The default stub provider is safe for local development and does not call an external service.
