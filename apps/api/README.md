# FinTrace API

FastAPI service boundary for FinTrace. Deterministic financial rules remain in application services; PostgreSQL is an explicit repository implementation and application startup never runs migrations.

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
| POST | `/api/v1/approvals/{request_id}/approve` | Apply one capability-authorized simulated approval |
| POST | `/api/v1/approvals/{request_id}/reject` | Apply one capability-authorized simulated rejection |
| GET | `/api/v1/audit-events` | Organization-scoped audit read for authorized roles |

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
- Migration 004 persists investigation/evaluation/control workflow snapshots, idempotency responses, and ordered tool calls. Audit events remain append-only. The default stub provider is safe for local development and does not call an external service.
