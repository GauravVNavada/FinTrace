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

The Python runtime is installed locally. Sprint 1 API/simulator tests run with the project virtual environment at `apps/api/.venv`. PostgreSQL migration execution remains pending until a local PostgreSQL instance is provisioned.

The persistence increment adds `fintrace-migrate`, `fintrace-seed`, the `/ready` dependency check, and a PostgreSQL repository path selected by `STORAGE_BACKEND=postgres`. The required database integration gate is: start `docker compose up -d postgres`, apply migrations, seed a fixed dataset, run the API against PostgreSQL, and exercise lifecycle, exception, graph, pattern, and audit paths. It is not marked complete until that live environment check runs.

Sprint 3 adds API contract coverage for the flagship cited investigation, same-key idempotency, missing tenant context, cross-tenant denial, invalid provider output, and provider unavailability. The test provider is deterministic; no external AI call is made.

Sprint 4 adds capability authorization, action allowlists, low/high/secondary approval policy, safe simulated approval, resolution idempotency conflicts, audit-event assertions, and concurrent duplicate-approval tests. The controls service is in memory until the migration runner and PostgreSQL test database are added.

Sprint 5 adds graph derivation and tenant isolation tests, deterministic pattern grouping and detail lookup, analytics capability checks, evaluation idempotency, hidden-ground-truth response assertions, and web route smoke checks. The browser smoke check verifies Patterns, Evaluations, and Audit loading/empty/populated states against a running Next.js server. The release script is exercised with a fixed seed and bounded 50-order run so its output is reproducible without PostgreSQL or an external AI provider.

CI now runs frontend quality gates, API tests/static checks, and dependency audits. Secret scanning and a live PostgreSQL CI integration job remain release-hardening follow-ups.
