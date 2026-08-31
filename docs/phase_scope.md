# FinTrace Phase Scope

Status: active product baseline · Sprints 0–7 local implementation complete · 2026-08-31

## Product evolution scope

The sections below describe the validated seeded-MVP baseline and the completed local data-driven evolution. Production hardening, live-provider credentials/operations, and an explicit labeled uploaded-dataset evaluation contract remain deployment/product extensions, not hidden implementation work.

### Domain vocabulary

- `FinancialInvestigation`: top-level company/time-period workspace.
- `ExceptionInvestigation`: evidence investigation of one unresolved exception.
- `ReconciliationRun`: deterministic execution over one dataset version.
- `EvaluationRun`: benchmark execution against hidden ground truth.

### Active sprint sequence

| Sprint | Scope | Status |
| --- | --- | --- |
| 0 | Domain vocabulary, architecture, documentation, constraints, and Sprint 1 contracts | Complete |
| 1 | Financial investigation workspace, secure CSV/XLSX upload, source metadata, and upload audit | Complete |
| 2 | Bounded source analysis, provider adapter, schema mapping, and confirmation UI | Complete: bounded provider boundary, honest offline/live-provider states, persisted proposals, explicit confirmation, API tests, and connected review UI |
| 3 | Relationship discovery, confirmation, canonical normalization, and lineage | Complete: deterministic proposals, standalone review, immutable dataset versions, lineage, decimal-safe money conversion, full generated source-type coverage, and explicit rejection of unknown/unjoinable rows are implemented. |
| 4 | Investigation-scoped lifecycle construction, reconciliation, persisted metrics, and dynamic dashboard | Complete: persisted idempotent run/results, deterministic normalized-record adapter, currency-aware metrics, investigation-scoped dashboard controls, and truthful loading/empty/unavailable states are implemented. The legacy seeded exception resource remains separate by design. |
| 5 | Real bounded AI exception investigation, visible tool trace, verification, and ambiguity refusal | Complete for the local/provider-adapter path: the configured provider selects only validated/capped read-only evidence tools; uploaded reconciliation results persist `SUPPORTED`/`UNRESOLVED`/`FAILED` through migration 010, support an opt-in OpenAI-compatible adapter, expose scoped retrieval and a controlled human-review/approval route, and show evidence/tool traces. Provider outage is an explicit unavailable state and ambiguity remains `UNRESOLVED`. The default local provider is explicitly deterministic/offline. |
| 6 | Derived patterns, exposure analytics, populated audit, and AI evaluation metrics | Complete for deterministic patterns, potential-exposure roll-up, audit population, and measured synthetic evaluation. Uploaded-dataset AI scoring is intentionally not enabled without a ground-truth label contract. |
| 7 | Explicit demo mode, fresh synthetic investigations, and final UX polish | Complete: fresh bounded synthetic generation, source/intake/relationship/reconciliation/investigation screens, honest demo copy, and browser-verified walkthrough are implemented. |

No sprint may be marked complete when its behavior is only visual, hardcoded, disconnected from persistence, or silently backed by fake AI.

The historical phase checklists below are the completion record for the seeded MVP baseline. They are retained for traceability and do not close the active evolution sprints above.

## Phase 0 — Product foundation (complete in this increment)

- [x] Turbo workspace with `apps/web` and `packages/ui`.
- [x] Next.js App Router shell with responsive serious-operations-console UX.
- [x] Typed domain adapter with reproducible benchmark-shaped demo data.
- [x] Dashboard, queue, detail, patterns, runs, evaluation, audit, and settings surfaces.
- [x] Reusable shadcn-style primitives: Button, Card, Badge, Progress.
- [x] Documentation set and decision log.
- [x] Centralized `packages/ui/src/components` component inventory, semantic token stylesheet, and app stylesheet import gate.
- [x] Functional UI actions for exports, evaluation/reconciliation runs, derived graph loading, queue search navigation, and header/help states.

## Phase 1 — P0 backend vertical slice (complete for MVP)

- [x] FastAPI service connected to PostgreSQL migrations.
- [x] Synthetic generator for 500+ lifecycles with seed 42 and hidden ground truth.
- [x] Canonical table migration and organization-scoped lifecycle boundary.
- [x] FastAPI lifecycle read boundary backed by the deterministic seed-42 adapter.
- [x] Deterministic reconciliation and evaluation runner.
- [x] Replace overview, exception queue/detail, patterns, evaluations, and audit reads with typed `/api/v1` clients where the corresponding API contract exists.
- [x] Persist investigations, evaluations, approvals, idempotency responses, and audit events in PostgreSQL.

Persistence increment status: migrations 001–010, the organization-scoped repository, explicit migration runner, deterministic seed command, readiness check, and local Compose database are implemented and exercised against Docker PostgreSQL on host port 55432. Investigation, source metadata, source analyses, mappings, relationship proposals, dataset versions, normalized records, reconciliation runs/results, uploaded exception investigations, evaluation, approval, idempotency, and audit records are durable in PostgreSQL mode; the demo repository implements the same contract in process for isolated tests.

Definition of done: clean checkout can seed, reconcile, expose the dashboard, inspect an exception, investigate one case, escalate an ambiguous case, and emit benchmark metrics.

Sprint 1 gate status: financial investigation create/list/get, safe CSV/XLSX inspection, generated storage references, source metadata persistence, tenant isolation, idempotent upload replay, source deletion, audit events, API contract tests, and live Uvicorn HTTP smoke test are complete.

Active evolution gate status: bounded CSV/XLSX analysis, inferred types, deterministic/offline classification, optional provider abstraction, mapping proposals, tenant-scoped edits, explicit confirmation, provider-failure handling, relationship proposals/decisions, immutable normalization with lineage, deterministic lifecycle construction, persisted idempotent reconciliation, durable uploaded-result investigation with dynamic validated tool plans, scoped retrieval, controlled review/approval, advisory patterns, exposure roll-up, audit, fresh source generation, and connected UI are implemented and tested. The legacy seeded exception queue is intentionally not a projection of uploaded investigations. Uploaded-dataset evaluation remains disabled until labels can be supplied through a reviewed contract; the synthetic benchmark remains the only public evaluation source.

MVP baseline Sprint 2 gate status: deterministic reconciliation, scenario coverage, hidden-ground-truth evaluation, metric output, Ruff/mypy checks, and live API smoke tests are complete. This historical baseline gate is separate from active evolution Sprint 2 (source analysis and mapping).

MVP baseline Sprint 3 gate status: allowlisted read-only tools, provider-neutral deterministic stub, strict controlled output validation with one retry, deterministic citation verifier/evidence score, safe provider failure, durable investigation/tool-call records, idempotent investigation requests, API retrieval routes, and live Uvicorn smoke tests are complete. No external AI provider is required for the MVP path.

Sprint 4 gate status: capability-level authorization, signed identity-claim verification, action allowlists, INR low/high/secondary approval policy, idempotent resolution/approval decisions, append-only audit events with authorized audit reads, PostgreSQL control persistence, and concurrent workflow tests are complete. `AUTH_MODE=required` is the deployment setting; development headers remain available only in explicit development mode.

## Phase 2 — Safety and evidence

- [x] Allowlisted investigation tools and provider abstraction.
- [x] Strict structured output validation and one retry on invalid output.
- [x] Deterministic verifier and evidence score.
- [x] RBAC capabilities and policy enforcement on the server.
- [x] Idempotency for evaluation, investigation, resolution, and approval endpoints with durable response replay in PostgreSQL.

## Phase 3 — Differentiation

- [x] Derived lifecycle graph from canonical lifecycle records, including explicit missing-step nodes.
- [x] Recurring pattern detector with deterministic grouping, exposure roll-up, and prevention recommendations.
- [x] API-backed audit/tool-call activity surface with durable PostgreSQL audit records.
- [x] Evaluation report API and reproducible PowerShell demo script.

## Explicitly deferred

Kafka, Kubernetes, microservices, graph databases, vector databases, custom model training, arbitrary SQL tools, real payment actions, real production connectors, natural-language finance Q&A, and advanced one-to-many matching.

## Change control

Scope changes require a written rationale, an updated phase checklist, and an update to `docs/PRD.md` if user-visible behavior or product scope changes. Implementation must not silently promote P1/P2 work into P0.

## Delivery sequence

### Sprint 0 — Foundation

Repository setup, design system, responsive shell, typed contracts, documentation, and CI-safe checks. Exit gate: every screen has a stable route and no component owns business rules.

### Historical MVP Sprint 1 — Data and persistence

Synthetic generator, canonical tables, migrations, tenant context, source normalization, and lifecycle resolver. Exit gate: 500+ seeded lifecycles can be queried by order ID and hidden ground truth is inaccessible to investigation code.

### Historical MVP Sprint 2 — Reconciliation and evaluation

Fee/tax/net arithmetic, timing windows, duplicate detection, exception creation, severity, exposure, and benchmark metrics. Exit gate: deterministic batch produces matched/variance/exception/ambiguous output without an AI provider.

Sprint 2 acceptance criteria:

- [x] A seeded batch produces one deterministic result per lifecycle.
- [x] Money is calculated from integer minor units with no floating-point arithmetic.
- [x] Known fee variance and late settlement are distinguishable from loss exceptions.
- [x] Duplicate and ambiguous payment candidates are never auto-matched.
- [x] Missing invoice, settlement, refund, and operational reversals produce controlled exception types.
- [x] Precision, recall, match rate, exception recall, throughput, and unresolved count are generated from hidden ground truth.
- [x] The benchmark runs without an AI provider or database connection.

### Historical MVP Sprint 3 — Investigation and API integration

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

### Historical MVP Sprint 4 — Controls and audit

RBAC capabilities, approval policy, idempotency, audit event persistence, and concurrent workflow tests.

Acceptance criteria:

- [x] API authorization resolves capability-level permissions from verified identity claims when bearer authentication is enabled; development headers are rejected when `AUTH_MODE=required`.
- [x] Development actor context enforces Analyst, Finance Manager, Controller, and Auditor capabilities at the service boundary.
- [x] INR approval policy applies low-value, high-value, secondary-approval, ambiguous, and duplicate-payment rules server-side.
- [x] Resolution requests, approvals, and rejections require idempotency keys and reject key reuse with a different request.
- [x] Concurrent approvals cannot create duplicate decisions by the same actor.
- [x] Important control events are recorded in the append-only demo audit adapter.
- [x] PostgreSQL migration defines membership, idempotency, approval-request, and approval-decision tables with organization-scoped constraints.
- [x] No control endpoint performs real financial or source-system mutation.

Exit gate: no unauthorized or duplicate consequential operation can succeed in the tested demo boundary. Durable PostgreSQL writes and verified claim verification have been exercised locally; managed identity and operational hardening remain deployment responsibilities.

### Historical MVP Sprint 5 — Differentiation and release evidence

Derived graph, pattern grouping, prevention recommendations, evaluation report, demo script, browser smoke evidence, and known limitations.

Sprint 5 gate status: derived graph, deterministic pattern grouping, API evaluation report, web API clients for the implemented resource surfaces, loading/error/empty states, Docker-backed API smoke tests, and the documented demo script are complete. Production operational hardening remains documented as deployment work rather than being represented as an application feature.

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
- [x] Visible export and run controls have a verified outcome or an explicit honest unavailable state; they are not inert placeholder buttons.

## Review gates

No phase is complete on UI appearance alone. Each gate requires implementation evidence, automated checks, documentation updates, and a short list of known limitations. A failing security or data-integrity gate blocks promotion regardless of frontend completeness.

The UI design-system gate for the current web surface is complete under ADR-004. The inventory, semantic token boundary, app stylesheet import gate, static architecture checks, production build, and browser smoke evidence are recorded in `docs/ui_component_inventory.md`. Future UI work must keep this gate green; production hardening remains a deployment responsibility.
