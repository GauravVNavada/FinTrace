# FinTrace Testing Strategy

**Status:** active · 2026-08-30

## Test pyramid

```text
                 Evaluation / scenario tests
              Integration: API -> service -> DB
           Unit: money, matching, severity, policy
       Static checks: typecheck, lint, dependency audit
```

## Required unit coverage

- Money normalization and decimal-safe arithmetic.
- Settlement gross/fee/tax/net calculations.
- Matching windows and late settlement behavior.
- Duplicate payment detection.
- Lifecycle completeness and exception type mapping.
- Exposure and severity calculation.
- Evidence score clamp and missing-evidence penalties.
- Approval policy thresholds and role capabilities.
- Idempotency key behavior.
- Reconciliation status mapping and evaluation metric calculations.

## Scenario fixtures

| Fixture | Expected result |
| --- | --- |
| clean_sale | `RECONCILED` |
| fee_variance | `RECONCILED_WITH_VARIANCE`, zero loss exposure |
| late_settlement | timing variance, not financial loss |
| missing_invoice | `EXCEPTION`, `ERP_INVOICE_MISSING` |
| duplicate_payment | `EXCEPTION`, human review |
| full_refund_correct | reconciled refund lifecycle |
| refund_inventory_missing | high exception, review required |
| partial_refund | exact line-item validation |
| ambiguous_payment | `AMBIGUOUS` / `UNRESOLVED`, never guess |
| provider_failure | deterministic evidence remains available |

Sprint 2 must also assert that a fixed seed produces byte-for-byte equivalent canonical outputs and that the evaluator never passes hidden ground truth into the reconciliation engine.

## Integration tests

The P0 integration path is:

```text
seed -> reconciliation run -> exception -> evidence query
     -> investigation -> verifier -> review request -> audit event
```

Each test uses an isolated organization and database transaction. Tests must include malformed IDs, missing records, provider timeout, duplicate request, concurrent approval, and cross-tenant access attempts.

## Frontend verification

- Route smoke tests for every screen in `docs/appflow.md`.
- Keyboard navigation and visible focus.
- Responsive layout at narrow, tablet, and desktop viewports.
- Filter behavior and filtered-empty state.
- Investigation result and AI-failure state.
- CSV export actions, evaluation/run API actions, derived graph loading, queue search navigation, and header/help state changes.
- No status meaning communicated by color alone.

## AI regression tests

Store representative exception fixtures and expected controlled codes. Assert that:

- every cited record exists;
- unsupported claims are rejected;
- invalid codes are rejected;
- missing evidence produces escalation;
- prompt-injection text in source data is inert.

## Commands

```text
pnpm typecheck
pnpm build
pnpm lint
cd apps/api && python -m pytest
cd apps/api && ruff check .
```

The Docker-backed end-to-end check is reproducible after starting the API in PostgreSQL mode:

```powershell
docker compose up -d postgres
cd apps/api
.venv\Scripts\fintrace-migrate.exe
.venv\Scripts\fintrace-seed.exe --orders 1000 --seed 42 --anomaly-rate 0.30 --organization-id ORG-001
$env:STORAGE_BACKEND = "postgres"
$env:DATABASE_URL = "postgresql://fintrace:fintrace@127.0.0.1:55432/fintrace"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# from a second terminal at the repository root:
./scripts/e2e-postgres.ps1
```

The Python runtime is installed locally. API/simulator tests run with `apps/api/.venv`; Docker PostgreSQL migrations 001–004 and seed-42 data have been applied locally.

The persistence increment adds `fintrace-migrate`, `fintrace-seed`, the `/ready` dependency check, and a PostgreSQL repository path selected by `STORAGE_BACKEND=postgres`. The live database gate has been run: Docker PostgreSQL was migrated and seeded, and HTTP smoke covered lifecycle, exception, investigation replay, evaluation replay, approval, and audit paths.

Sprint 3 adds API contract coverage for the flagship cited investigation, same-key idempotency, missing tenant context, cross-tenant denial, invalid provider output, and provider unavailability. The test provider is deterministic; no external AI call is made.

Sprint 4 adds capability authorization, signed bearer-claim verification, action allowlists, low/high/secondary approval policy, safe simulated approval, durable resolution idempotency conflicts, audit-event assertions, and concurrent duplicate-approval tests.

Sprint 5 adds graph derivation and tenant isolation tests, deterministic pattern grouping and detail lookup, analytics capability checks, evaluation idempotency, hidden-ground-truth response assertions, and web route smoke checks. The browser smoke check verifies Patterns, Evaluations, and Audit loading/empty/populated states against a running Next.js server. The release script is exercised with a fixed seed and bounded 50-order run so its output is reproducible without PostgreSQL or an external AI provider. CI also provisions PostgreSQL, applies migrations, seeds a bounded dataset, and runs `tests/test_postgres_integration.py`.

CI now runs frontend quality gates, API tests/static checks, and dependency audits. Secret scanning and a live PostgreSQL CI integration job remain release-hardening follow-ups.
