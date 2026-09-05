# FinTrace Architecture

## Investigation evidence improvement (2026-09-05)

Provider recovery: malformed final candidates receive one bounded schema-correction turn; Groq JSON-generation failures receive one compact regeneration. Ambiguous synthesis uses JSON output after mandatory retrieval with up to 12 citations and a 5,000-token response budget. Formatting failures are distinguished from outages. Any FAILED persisted assessment can be retried with a new idempotency key, preserving its identity; same-key replays remain unchanged. The UI exposes retry even after evidence lookups completed.

InvestigationService collects five mandatory scoped lookups for ambiguous associations before provider synthesis. Baseline ToolCall metadata identifies deterministic-evidence-collection / none; the response retains the actual AI provider/model. Only unused tools remain selectable. The verifier rejects missing order/candidate/settlement field citations. Free-text hypotheses are advisory; field verification is not proof of narrative causation.

Status: accepted local product architecture; Sprints 0–7 plus Track 4 reliability/UX hardening implemented · 2026-09-03

## Decision summary

FinTrace uses a modular monorepo with one Next.js web application, one FastAPI API service, a shared UI package, and a versioned backend contract. The MVP does not introduce microservices beyond the web/API boundary, queues, graph databases, vector databases, or Kubernetes. A relational model is sufficient for canonical entities; the lifecycle graph is derived for presentation.

## Evolution target

The existing baseline is extended with an investigation-scoped ingestion pipeline. The top-level `FinancialInvestigation` owns source files, analysis, mappings, relationship proposals, dataset versions, reconciliation runs, exceptions, patterns, and audit history. `ExceptionInvestigation` remains a separate child workflow for evidence analysis of one exception.

```text
FinancialInvestigation
  → source files and source analysis
  → confirmed mappings and relationships
  → normalized dataset version
  → lifecycle construction
  → ReconciliationRun
  → exceptions and patterns
  → ExceptionInvestigation
  → review controls and audit
```

Uploaded source content is untrusted input. Classification and mapping receive bounded metadata, headers, inferred types, statistics, row count, and limited representative samples; full files are not sent to Gemini. Deterministic relationship evidence and canonical normalization remain authoritative. Exception investigation starts with deterministic findings, then Gemini requests one allowlisted read-only tool per turn until it concludes or reaches the strict eight-call limit. AI may provide semantic interpretation but cannot establish monetary truth, authorization, or state transitions. Every cited field/operator/value claim is checked against the scoped lifecycle before a supported result can persist.

## System shape

```text
Synthetic generator / source adapters
              |
              v
       Normalization layer
              |
              v
      Canonical lifecycle model
              |
              v
    Deterministic reconciliation
        |                 |
        v                 v
    Matched          Exception queue
                            |
                            v
              Bounded investigation tools
                            |
                            v
                 Structured AI result
                            |
                            v
             Deterministic verifier + policy
                      |             |
                      v             v
                Human review     Audit event
```

## Repository boundaries

`apps/web` owns route composition, loading/error boundaries, interaction state, and presentation. It consumes domain-shaped data and must not encode reconciliation rules in components.

`packages/ui` owns reusable presentation primitives. Primitives are intentionally small and accessible, following shadcn conventions: composable React components, Tailwind classes, and no product-specific data.

### Design-system ownership

The complete shared UI boundary is `packages/ui/src`. Reusable primitives live in its focused `components/` directory; the public barrel, `cn`, Tailwind preset, and `global.css` remain directly under `src`. Components are organized as focused files such as `components/button.tsx`, `components/card.tsx`, `components/badge.tsx`, and `components/progress.tsx`; a primitive's supported variants stay in its own file rather than being scattered across apps.

`packages/ui/src/global.css` is the only source of global CSS and design tokens. It defines semantic CSS variables, base styles, accessibility states, and theme selectors. Tailwind semantic utilities map to those variables through the shared UI preset. Components never contain literal color values, palette utilities, or inline color styles. Product apps compose the primitives and may select a theme with a data attribute, but may not redefine tokens or create local primitive copies. The current inventory and verification evidence live in `docs/ui_component_inventory.md`.

Each app's `app/globals.css` must contain exactly one import of the UI package stylesheet and no other declarations. This keeps multiple apps consistent while allowing app-specific themes through namespaced selectors in the shared token file, for example `[data-theme="operations"]` and `[data-theme="review"]`.

`docs` owns the durable decisions. A change to product behavior must update the PRD and the relevant contract document in the same change.

`apps/api` owns source ingestion boundaries, bounded source analysis, normalization, lifecycle resolution, reconciliation, investigation orchestration, policy, persistence, and audit writes. The frontend consumes `/api/v1` only and never connects directly to a database.

### Reliability boundary update

Consequential source workflow mutations reserve an idempotency lease before expensive work, persist or replay only a request-hash-compatible response, and release the lease on failure. PostgreSQL leases reclaim expired pending work. Tenant integrity is enforced both in repository predicates and in composite organization-aware foreign keys added by migration 014. Evaluation and audit screens treat empty, forbidden, and unavailable states as different domain outcomes. The local demo remains explicitly process-local; PostgreSQL is required for restart durability.

## Runtime and deployment

The web app is a Next.js App Router application and can be deployed as a Node process. The intended production shape is one deployable web/API surface backed by PostgreSQL. A background worker can be added when synchronous reconciliation and investigation are proven insufficient; it is not part of the foundation.

## Trust boundaries

1. Source records are untrusted data, not instructions.
2. Tool calls are allowlisted, parameter validated, organization scoped, read-only, rate bounded, and logged.
3. AI output is untrusted until it passes schema validation and deterministic verification.
4. Only policy-authorized server actions can create approval or resolution effects.
5. Audit events are append-only at the application level.

## Consequence

This architecture makes AI failure non-fatal. If an AI provider is unavailable, `/api/v1/ai/provider-health` exposes the configured state before a demo starts, and investigation responses persist `FAILED` with a redacted error category, retryability, stage, iteration, and latency. Reconciliation, exception evidence, exposure, timeline, manual review, and audit remain available.

## Stack matrix

| Component | Language/runtime | Framework | Database/storage | Important configuration |
| --- | --- | --- | --- | --- |
| `apps/web` | TypeScript, Node 24+ | Next.js App Router, React, Tailwind | Typed API responses with deterministic fallback for isolated development | `NEXT_PUBLIC_API_BASE_URL`, organization/actor dev context |
| `apps/api` | Python 3.12+ | FastAPI, Pydantic, psycopg 3 | PostgreSQL 16+ for the buildathon/demo runtime; demo adapter remains available for tests/offline fixtures | `DATABASE_URL`, `STORAGE_BACKEND`, `ALLOWED_ORIGINS`, `API_PREFIX` |
| `packages/ui` | TypeScript, React | Tailwind + shadcn-style primitives | None | Shared by web apps only |
| Evaluation runner | Python 3.12+ | Plain Python modules | Synthetic CSV/JSON and hidden ground truth | deterministic seed and output path |
| AI provider adapter | Python | `AIProvider` with `GeminiProvider`, `GroqProvider`, and test-only `StubAIClient` | No prompt/result persistence outside API model; provider/model selected at runtime | timeout, retry, model, redaction settings |

## Service directory contract

```text
apps/
├── web/
│   ├── app/                 # routes and document shell
│   ├── components/          # product UI composition
│   └── lib/                 # typed adapter and view contracts
└── api/
    ├── app/
    │   ├── api/deps.py      # auth/tenant dependencies
    │   ├── api/v1/          # versioned HTTP routes
    │   ├── core/             # settings and cross-cutting infrastructure
    │   ├── domain/           # enums and transport-safe schemas
    │   ├── investigations/   # tools, provider adapter, verifier, service
    │   ├── controls/         # capabilities, approval policy, idempotency, audit
    │   ├── graph/            # derived lifecycle graph schemas and service
    │   ├── patterns/         # deterministic recurring-signal grouping
    │   ├── evaluation/       # bounded synthetic evaluation API and report service
    │   └── repositories/     # persistence adapter boundary
    └── tests/                # API contract tests
packages/
└── ui/
    └── src/
        ├── components/      # focused reusable shadcn-style primitives
        │   ├── button.tsx   # all Button variants and sizes
        │   ├── card.tsx     # Card family
        │   └── ...          # every current reusable primitive
        ├── global.css       # tokens, themes, reset, shared global styles
        ├── tailwind.preset.ts
        ├── utils.ts
        └── index.ts         # public exports only
```

The API exposes `/health`, `/ready`, demo-login, dashboard/exception/lifecycle reads, financial-investigation source/generation/normalization/reconciliation routes, investigation routes, controls/audit routes, and graph/pattern/evaluation routes. `STORAGE_BACKEND=postgres` selects the organization-scoped PostgreSQL repository for the buildathon/demo runtime; `STORAGE_BACKEND=demo` keeps the deterministic in-process adapter available for tests and offline fixtures. The graph and pattern services are derived application views over canonical lifecycle data; they do not introduce a graph database. Bearer claim verification is enabled per `AUTH_MODE`.

## Request-to-data path

1. FastAPI receives the request and assigns a request correlation ID.
2. Authentication verifies the session/token and resolves organization, actor, and capabilities.
3. Route dependencies validate path, query, and body types.
4. Application service applies business policy and passes organization scope explicitly to the repository.
5. Repository executes parameterized, bounded queries and returns domain objects.
6. Consequential writes run in a transaction, enforce idempotency, and append an audit event.
7. The response serializer emits only the public contract; internal stack traces and provider payloads stay server-side.

For Sprint 5 analytics, the graph service first applies organization scope and lifecycle lookup, then derives bounded nodes/edges. The pattern service reconciles the organization-scoped lifecycle set and groups stable exception signatures. The evaluation service alone can access hidden labels; its public report contains metrics, never ground-truth records.

Inventory valuation follows the same boundary: source analysis and normalization preserve optional `unit_cost_minor` and `inventory_value_minor`, reconciliation derives cost-basis expectations using integer arithmetic, and bounded AI receives only the resulting scoped evidence. Providers cannot alter inventory, financial state, or deterministic exception status.

## Failure and timeout policy

Database, provider, and external source calls require explicit timeouts. Retries are only allowed for safe, idempotent transient operations with bounded backoff and configured-key rotation. Daily quota exhaustion, authorization, unsupported-model, malformed tool arguments, verifier rejection, and invalid FinTrace input are not retried or hidden by fallback. Provider failure returns a typed investigation-unavailable state with no credential or provider payload logging; it never changes reconciliation state or triggers a resolution. Provider health performs one bounded structured/tool-capability probe per provider and caches the result briefly.

## Deployment stages

| Stage | Web | API | Storage | Evidence required |
| --- | --- | --- | --- | --- |
| Local foundation | Next dev server | optional FastAPI scaffold | in-memory demo adapter | browser smoke check |
| Local P0 | Next dev server | Uvicorn | local PostgreSQL | `fintrace-migrate`, `fintrace-seed`, lifecycle/investigation/control/evaluation/audit smoke |
| Staging | Node deployment | containerized API | managed PostgreSQL | migration and security checks |
| Production candidate | immutable build | separately deployable API | encrypted PostgreSQL + backups | load, auth, tenant, recovery tests |
