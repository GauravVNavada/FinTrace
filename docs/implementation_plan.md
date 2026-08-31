# FinTrace Implementation Plan

**Status:** Active local product baseline · Sprints 0–7 implemented · 2026-08-31

## Objective

Evolve FinTrace from a seeded exception demo into a data-driven financial lifecycle investigation platform without replacing the existing deterministic reconciliation and evidence-verification foundations.

## Delivery sequence

| Sprint | Deliverable | Exit gate |
| --- | --- | --- |
| 0 | Domain vocabulary, documentation, boundaries, security constraints, and Sprint 1 contracts | Complete: documentation is consistent and the domain boundaries are explicit. |
| 1 | FinancialInvestigation workspace and CSV/XLSX source upload | Complete: create, upload, refresh, list, audit, delete, and reject unsafe input end to end. |
| 2 | Bounded source analysis, provider adapter, schema mapping, and confirmation | Complete: bounded provider boundary, explicitly labelled offline/live-provider states, persisted proposals, explicit confirmation, API tests, and connected review UI. |
| 3 | Relationship discovery, confirmation, canonical normalization, and lineage | Complete: deterministic proposals, explicit decisions, immutable versions, lineage, decimal-safe conversion, generated source-type coverage, and refusal of unknown/unjoinable rows are covered. |
| 4 | Investigation-scoped lifecycle construction and reconciliation | Complete: persisted idempotent run/results, deterministic lifecycle construction, currency-aware metrics, and connected investigation-scoped overview controls are covered. The seeded compatibility queue remains separate by design. |
| 5 | Real bounded AI exception investigation | Complete for the local/provider-adapter path: the configured provider selects only validated allowlisted tools, uploaded results produce validated evidence-backed responses or explicit `UNRESOLVED`, provider outages produce explicit `FAILED`/unavailable responses, outcomes persist, scoped retrieval and read-only traces are exposed, and unresolved uploaded results can enter the controlled review/approval route. The default provider is explicitly offline; live provider use is opt-in configuration. |
| 6 | Derived patterns, exposure analytics, audit population, and AI evaluation | Complete for deterministic advisory patterns, exposure roll-up, populated audit, and measured synthetic evaluation. Uploaded-dataset scoring is not enabled without a reviewed label contract. |
| 7 | Explicit demo mode and UX polish | Complete: fresh bounded synthetic generation, connected source-to-investigation routes, honest states, and browser walkthrough verification are implemented. |

## Per-sprint protocol

1. Inspect and reuse existing modules.
2. Update affected source-of-truth markdown before implementation.
3. Define migrations, API contracts, UI routes, and failure states.
4. Implement backend behavior before visual polish.
5. Add unit, integration, security, and route tests.
6. Run API tests, lint, typecheck, build, migrations, and smoke checks.
7. Manually verify the primary flow.
8. Update implementation status and report only genuine remaining issues.

## Explicit non-goals

Do not add Kafka, Kubernetes, microservices, graph/vector databases, arbitrary SQL tools, real money movement, or a generic chatbot. Background jobs may be introduced only if measured synchronous processing becomes insufficient.
