# FinTrace Testing Strategy

**Status:** active; local Sprints 0–7 path plus Track 4 hardening verified · 2026-09-03

## Evolution test path

The implemented end-to-end path is tested as one vertical slice:

```text
create financial investigation
  → upload valid CSV/XLSX
  → reject invalid/oversized/malformed input
  → persist metadata after refresh
  → analyze bounded samples
  → confirm mappings and relationships
  → normalize with lineage
  → reconcile and investigate
  → unresolved/ambiguous result → request review → approve or reject
```

Sprint 1 includes multipart validation, safe filename/path tests, empty/malformed file tests, organization isolation, idempotent upload behavior, metadata persistence, and audit assertions. Sprint 2 adds bounded CSV/XLSX analysis, inferred types, classification/provider status, mapping proposals, required-field blocking, edit/confirmation behavior, provider failure, persistence, and tenant-scope tests. Sprint 3–6 tests cover relationship decisions, normalization lineage, decimal-safe money conversion, reconciliation persistence, uploaded-result investigations, dynamic bounded tool selection, provider key-pool/fallback behavior, explicit `UNRESOLVED` ambiguity, controlled review/approval, patterns, audit, and hidden-label isolation. Sprint 7 tests bounded fresh generation through the same upload path and the browser flow. Browser verification checks source statuses and populated/empty/unavailable states rather than only checking that a dropzone renders.

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

Every month in the reusable export pack intentionally includes at least one `AMBIGUOUS_PAYMENT_ASSOCIATION` lifecycle. Uploading any month’s seven source exports and running the close must produce at least one `NEEDS EVIDENCE` result; each case is intentionally unresolved because two captured payment candidates are associated with the order and the available records do not establish which one is valid. Each monthly pack keeps its other clean, variance, and exception cases alongside the ambiguity case.

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
pnpm test:e2e
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

The Python runtime is installed locally. API/simulator tests run with `apps/api/.venv`; Docker PostgreSQL migrations 001–010 and seed-42 data are the local persistence verification path.

The current local API contract test run is `85 passed, 3 skipped` (2026-09-03). It includes demo-login role enforcement, required idempotency headers for every source mutation, request-hash replay/conflict behavior, independent-approver enforcement, organization-scoped reads, and the Track 4 workflow. The PostgreSQL path must apply migration 014 before release verification; the demo adapter is process-local and is not restart durability.

## Verified local release evidence

On 2026-08-31 the repository was verified with:

- API: Ruff clean, mypy clean across 82 source files, `53 passed, 3 skipped`.
- PostgreSQL: migrations applied with `Applied 0 migration(s): none`; the three-test vertical slice passed with `STORAGE_BACKEND=postgres` and `FINTRACE_TEST_DATABASE_URL` set.
- Web: lint clean, typecheck clean, UI architecture checks passed, and production build generated all 15 routes.
- Browser: the mocked-AI golden path passes Controller login, flagship launch, investigation overview, reconciliation, exception investigation, human review, and audit; the clean production server also passes primary-route smoke checks.

The browser walkthrough used the in-process demo backend; PostgreSQL persistence was separately exercised by the integration suite. The default AI provider was the explicitly labelled deterministic local provider, so no live external AI call is claimed.

The persistence increment adds `fintrace-migrate`, `fintrace-seed`, the `/ready` dependency check, and a PostgreSQL repository path selected by `STORAGE_BACKEND=postgres`. The live database gate covers migration/seed, lifecycle and exception reads, financial-investigation source upload/delete, source-analysis/mapping persistence, investigation replay, evaluation replay, approval, and audit paths.

Sprint 3 adds relationship proposal generation, confirmed-mapping gating, explicit decisions, immutable dataset versions, decimal-safe money conversion, lineage, malformed-value refusal, unknown/unjoinable-row refusal, tenant isolation, and audit assertions. Sprint 4 adds investigation-scoped deterministic lifecycle construction, persisted reconciliation runs/results, idempotency, currency-aware metrics, and result retrieval. Sprint 5 adds uploaded-result investigation through provider-selected, allowlisted evidence tools, strict plan/result verification, safe `UNRESOLVED` output for ambiguity, explicit `FAILED`/503 behavior for provider outage, durable investigation responses, scoped retrieval, read-only trace display, the uploaded-result review/approval route, and provider key-pool/fallback behavior. Sprint 6 adds deterministic advisory pattern grouping and exposure roll-up. Sprint 7 adds source generation, scenario selection, generator idempotency/conflict behavior, and browser workflow verification. The test provider is deterministic; live provider probes are separate and never consume the deterministic test suite.

Sprint 4 adds capability authorization, signed bearer-claim verification, action allowlists, low/high/secondary approval policy, safe simulated approval, durable resolution idempotency conflicts, audit-event assertions, and concurrent duplicate-approval tests.

Sprint 5 adds graph derivation and tenant isolation tests, deterministic pattern grouping and detail lookup, analytics capability checks, evaluation idempotency, hidden-ground-truth response assertions, and web route smoke checks. The browser smoke check verifies Patterns, Evaluations, and Audit loading/empty/populated states against a running Next.js server. The release script is exercised with a fixed seed and bounded 50-order run so its output is reproducible without PostgreSQL or an external AI provider. CI also provisions PostgreSQL, applies migrations, seeds a bounded dataset, and runs `tests/test_postgres_integration.py`.

CI now runs frontend quality gates, API tests/static checks, dependency audits, the mocked-AI browser golden path, and the PostgreSQL integration suite including the upload-to-reconciliation-to-investigation vertical slice. The local release scan found no credential-shaped matches outside ignored runtime secrets.
# Lifecycle mismatch benchmark checks

- Regenerate the eight monthly packs and assert each month contains one to three anomalous lifecycles.
- Assert inventory `inventory_value` equals `unit_cost * quantity` for healthy rows and that each injected mismatch is detectable without reading hidden ground truth.
- Exercise missing inventory return, wrong return value, wrong return quantity, inventory restored without refund, and ambiguous payment cases.
- Verify live investigation metadata identifies the actual provider/model; deterministic fixtures are restricted to explicitly offline tests.
