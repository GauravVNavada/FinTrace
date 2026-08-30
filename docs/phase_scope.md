# FinTrace Phase Scope

Status: active delivery plan · 2026-08-30

## Phase 0 — Product foundation (complete in this increment)

- [x] Turbo workspace with `apps/web` and `packages/ui`.
- [x] Next.js App Router shell with responsive serious-operations-console UX.
- [x] Typed domain adapter with reproducible benchmark-shaped demo data.
- [x] Dashboard, queue, detail, patterns, runs, evaluation, audit, and settings surfaces.
- [x] Reusable shadcn-style primitives: Button, Card, Badge, Progress.
- [x] Documentation set and decision log.
- [x] Centralized `packages/ui/src` component inventory, semantic token stylesheet, and app stylesheet import gate.

## Phase 1 — P0 backend vertical slice (in progress: persistence hardening)

- [ ] FastAPI service connected to PostgreSQL migrations.
- [x] Synthetic generator for 500+ lifecycles with seed 42 and hidden ground truth.
- [x] Canonical table migration and organization-scoped lifecycle boundary.
- [x] FastAPI lifecycle read boundary backed by the deterministic seed-42 adapter.
- [x] Deterministic reconciliation and evaluation runner.
- [ ] Replace demo adapter with `/api/v1` client.
- [ ] Persist exceptions, investigations, approvals, and audit events.

Persistence increment status: the PostgreSQL driver, organization-scoped repository path, explicit migration runner, deterministic seed command, readiness check, and local Compose database definition are implemented. The checkbox above remains open until a live PostgreSQL migration/seed/API run is executed; investigation/control/evaluation durability is intentionally still open.

Definition of done: clean checkout can seed, reconcile, expose the dashboard, inspect an exception, investigate one case, escalate an ambiguous case, and emit benchmark metrics.

Sprint 1 demo-boundary gate status: generator, migration definition, canonical lifecycle query, tenant isolation, API contract tests, 500-record CLI generation, and live Uvicorn HTTP smoke test are complete, so the deterministic demo-boundary sprints proceeded. Applying the migration to PostgreSQL remains the separate production-persistence gate because no PostgreSQL server is installed on this workstation; this does not represent a completed production database integration.

Sprint 2 gate status: deterministic reconciliation, scenario coverage, hidden-ground-truth evaluation, metric output, Ruff/mypy checks, and live API smoke tests are complete. The benchmark runs without AI or database connectivity, as required. PostgreSQL persistence remains an environment-dependent follow-up before production deployment.

Sprint 3 gate status: allowlisted read-only tools, provider-neutral deterministic stub, strict controlled output validation with one retry, deterministic citation verifier/evidence score, safe provider failure, in-process audit events, idempotent investigation requests, API retrieval routes, and live Uvicorn smoke tests are complete. The result store and audit events are intentionally in memory until the PostgreSQL persistence/audit sprint; no external AI provider is called.

Sprint 4 gate status: capability-level development authorization, action allowlists, INR low/high/secondary approval policy, idempotent resolution/approval decisions, append-only in-process audit events with authorized audit reads, PostgreSQL control migration, and concurrent workflow tests are complete. Verified identity claims and durable PostgreSQL writes remain deployment prerequisites.

## Phase 2 — Safety and evidence

- [x] Allowlisted investigation tools and provider abstraction.
- [x] Strict structured output validation and one retry on invalid output.
- [x] Deterministic verifier and evidence score.
- [x] RBAC capabilities and policy enforcement on the server.
- [x] Idempotency for resolution and approval endpoints; reconciliation-run persistence remains pending.

## Phase 3 — Differentiation

- [x] Derived lifecycle graph from canonical lifecycle records, including explicit missing-step nodes.
- [x] Recurring pattern detector with deterministic grouping, exposure roll-up, and prevention recommendations.
- [x] API-backed audit/tool-call activity surface; durable persisted audit records remain pending.
- [x] Evaluation report API and reproducible PowerShell demo script.

## Explicitly deferred

Kafka, Kubernetes, microservices, graph databases, vector databases, custom model training, arbitrary SQL tools, real payment actions, real production connectors, natural-language finance Q&A, and advanced one-to-many matching.

## Change control

Scope changes require a written rationale, an updated phase checklist, and an update to `docs/PRD.md` if user-visible behavior or product scope changes. Implementation must not silently promote P1/P2 work into P0.

## Delivery sequence

### Sprint 0 — Foundation

Repository setup, design system, responsive shell, typed contracts, documentation, and CI-safe checks. Exit gate: every screen has a stable route and no component owns business rules.

### Sprint 1 — Data and persistence

Synthetic generator, canonical tables, migrations, tenant context, source normalization, and lifecycle resolver. Exit gate: 500+ seeded lifecycles can be queried by order ID and hidden ground truth is inaccessible to investigation code.

### Sprint 2 — Reconciliation and evaluation

Fee/tax/net arithmetic, timing windows, duplicate detection, exception creation, severity, exposure, and benchmark metrics. Exit gate: deterministic batch produces matched/variance/exception/ambiguous output without an AI provider.

Sprint 2 acceptance criteria:

- [x] A seeded batch produces one deterministic result per lifecycle.
- [x] Money is calculated from integer minor units with no floating-point arithmetic.
- [x] Known fee variance and late settlement are distinguishable from loss exceptions.
- [x] Duplicate and ambiguous payment candidates are never auto-matched.
- [x] Missing invoice, settlement, refund, and operational reversals produce controlled exception types.
- [x] Precision, recall, match rate, exception recall, throughput, and unresolved count are generated from hidden ground truth.
- [x] The benchmark runs without an AI provider or database connection.

### Sprint 3 — Investigation and API integration

Allowlisted tools, AI provider abstraction, structured result validation, verifier, API client, and graceful failure.

Acceptance criteria:

- [x] Investigation requests require authenticated organization context and an `Idempotency-Key`.
- [x] The investigation service uses only named, read-only, organization-scoped tools.
- [x] Provider output is parsed into a strict schema and controlled root-cause/action codes.
- [x] The verifier independently checks cited record IDs, organization ownership, evidence compatibility, and missing/contradictory evidence.
- [x] Evidence scores are computed by deterministic server policy; the provider cannot supply a score.
- [x] Provider timeout/unavailability returns a safe failure without changing reconciliation or source-system state.
- [x] A flagship refund exception returns cited evidence through the API; invalid or ambiguous results become unresolved and require review.
- [x] Repeated requests with the same idempotency key return the same investigation result.

Exit gate: one flagship exception returns cited evidence; invalid/ambiguous/provider-failed results remain inspectable and require human review; backend and frontend quality gates pass.

### Sprint 4 — Controls and audit

RBAC capabilities, approval policy, idempotency, audit event persistence, and concurrent workflow tests.

Acceptance criteria:

- [ ] API authorization resolves capability-level permissions from verified identity claims.
- [x] Development actor context enforces Analyst, Finance Manager, Controller, and Auditor capabilities at the service boundary.
- [x] INR approval policy applies low-value, high-value, secondary-approval, ambiguous, and duplicate-payment rules server-side.
- [x] Resolution requests, approvals, and rejections require idempotency keys and reject key reuse with a different request.
- [x] Concurrent approvals cannot create duplicate decisions by the same actor.
- [x] Important control events are recorded in the append-only demo audit adapter.
- [x] PostgreSQL migration defines membership, idempotency, approval-request, and approval-decision tables with organization-scoped constraints.
- [x] No control endpoint performs real financial or source-system mutation.

Exit gate: no unauthorized or duplicate consequential operation can succeed in the tested demo boundary. Durable PostgreSQL writes and verified identity claims remain deployment prerequisites.

### Sprint 5 — Differentiation and release evidence

Derived graph, pattern grouping, prevention recommendations, evaluation report, demo script, browser smoke evidence, and known limitations.

Sprint 5 gate status: derived graph, deterministic pattern grouping, API evaluation report, web API clients, loading/error/empty states, and the documented demo script are complete. The clean-checkout reproduction gate is met for the in-process demo boundary; PostgreSQL-backed repositories, verified identity claims, and durable audit persistence remain explicit deployment prerequisites.

Sprint 5 acceptance criteria:

- [x] `GET /api/v1/exceptions/{id}/graph` derives bounded nodes and edges from organization-scoped canonical lifecycle data without a graph database.
- [x] Missing lifecycle steps are represented as explicit `MISSING` nodes rather than inferred as completed work.
- [x] `GET /api/v1/patterns` groups repeatable exception signals deterministically and returns only groups with at least two occurrences.
- [x] Pattern exposure is calculated from integer minor-unit reconciliation values and recommendations are labeled advisory/signal-only.
- [x] Pattern and graph endpoints reject missing or unauthorized organization context and do not leak cross-tenant resources.
- [x] `POST /api/v1/evaluation/run` accepts bounded dataset parameters, requires an idempotency key, and does not return hidden ground truth.
- [x] Patterns, Evaluations, and Audit screens consume typed API clients and expose loading, failure, empty, and populated states appropriate to each resource.
- [x] `scripts/demo.ps1` reproduces generation and benchmark evaluation with a documented seed, output path, and expected result shape.
- [x] Automated API tests, static checks, production build, live API smoke tests, and browser route smoke tests pass.
- [x] Known limitations and the distinction between demo/in-process behavior and production requirements are recorded in the PRD, architecture, API, testing, and demo documents.

## Review gates

No phase is complete on UI appearance alone. Each gate requires implementation evidence, automated checks, documentation updates, and a short list of known limitations. A failing security or data-integrity gate blocks promotion regardless of frontend completeness.

The UI design-system gate for the current web surface is complete under ADR-006. The inventory, semantic token boundary, app stylesheet import gate, static architecture checks, production build, and browser smoke evidence are recorded in `docs/ui_component_inventory.md`. Future UI work must keep this gate green; completion of this gate does not imply that deferred backend persistence, verified identity, or production deployment prerequisites are complete.
