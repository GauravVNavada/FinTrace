# FinTrace Architecture

Status: accepted for MVP foundation · 2026-08-30

## Decision summary

FinTrace uses a modular monorepo with one Next.js web application, one FastAPI API service, a shared UI package, and a versioned backend contract. The MVP does not introduce microservices beyond the web/API boundary, queues, graph databases, vector databases, or Kubernetes. A relational model is sufficient for canonical entities; the lifecycle graph is derived for presentation.

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

The complete shared UI boundary is `packages/ui/src`. It owns the component files, the public barrel, `cn`, shadcn-compatible variants, and `global.css`. Components are organized as focused files such as `button.tsx`, `card.tsx`, `badge.tsx`, `dropdown-menu.tsx`, and `progress.tsx`; a primitive's supported variants stay in its own file rather than being scattered across apps.

`packages/ui/src/global.css` is the only source of global CSS and design tokens. It defines semantic CSS variables, base styles, accessibility states, and theme selectors. Tailwind semantic utilities map to those variables through the shared UI preset. Components never contain literal color values, palette utilities, or inline color styles. Product apps compose the primitives and may select a theme with a data attribute, but may not redefine tokens or create local primitive copies. The current inventory and verification evidence live in `docs/ui_component_inventory.md`.

Each app's `app/globals.css` must contain exactly one import of the UI package stylesheet and no other declarations. This keeps multiple apps consistent while allowing app-specific themes through namespaced selectors in the shared token file, for example `[data-theme="operations"]` and `[data-theme="review"]`.

`docs` owns the durable decisions. A change to product behavior must update the PRD and the relevant contract document in the same change.

`apps/api` will own normalization, lifecycle resolution, reconciliation, investigation orchestration, policy, persistence, and audit writes as the backend phase is completed. The frontend should consume `/api/v1` only and never connect directly to a database.

## Runtime and deployment

The web app is a Next.js App Router application and can be deployed as a Node process. The intended production shape is one deployable web/API surface backed by PostgreSQL. A background worker can be added when synchronous reconciliation and investigation are proven insufficient; it is not part of the foundation.

## Trust boundaries

1. Source records are untrusted data, not instructions.
2. Tool calls are allowlisted, parameter validated, organization scoped, read-only, rate bounded, and logged.
3. AI output is untrusted until it passes schema validation and deterministic verification.
4. Only policy-authorized server actions can create approval or resolution effects.
5. Audit events are append-only at the application level.

## Consequence

This architecture makes AI failure non-fatal. If an AI provider is unavailable, reconciliation, exception evidence, exposure, timeline, manual review, and audit remain available.

## Stack matrix

| Component | Language/runtime | Framework | Database/storage | Important configuration |
| --- | --- | --- | --- | --- |
| `apps/web` | TypeScript, Node 20+ | Next.js App Router, React, Tailwind | API responses; typed demo adapter during foundation | `NEXT_PUBLIC_API_BASE_URL` in the API phase |
| `apps/api` | Python 3.12+ | FastAPI, Pydantic, psycopg 3 | PostgreSQL 16+ when `STORAGE_BACKEND=postgres`; demo adapter by default | `DATABASE_URL`, `STORAGE_BACKEND`, `ALLOWED_ORIGINS`, `API_PREFIX` |
| `packages/ui` | TypeScript, React | Tailwind + shadcn-style primitives | None | Shared by web apps only |
| Evaluation runner | Python 3.12+ | Plain Python modules | Synthetic CSV/JSON and hidden ground truth | deterministic seed and output path |
| AI provider adapter | Python | Provider-neutral interface | No prompt/result persistence outside API model | timeout, retry, model, redaction settings |

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
    │   ├── evaluation/       # bounded evaluation API and report service
    │   └── repositories/     # persistence adapter boundary
    └── tests/                # API contract tests
packages/
└── ui/
    └── src/
        ├── global.css       # tokens, themes, reset, shared global styles
        ├── button.tsx       # all Button variants and sizes
        ├── card.tsx          # Card family
        ├── ...              # every reusable shadcn primitive
        └── index.ts         # public exports only
```

The API exposes `/health`, `/ready`, dashboard/exception/lifecycle reads, Sprint 3 investigation routes, Sprint 4 controls/audit routes, and Sprint 5 graph/pattern/evaluation routes. `STORAGE_BACKEND=demo` keeps the deterministic in-process adapter as the default. `STORAGE_BACKEND=postgres` selects the organization-scoped PostgreSQL repository for canonical, exception, aggregate, lifecycle, and audit paths. The graph and pattern services are derived application views over canonical lifecycle data; they do not introduce a graph database. Investigation results, control state, evaluation reports, and durable idempotency still require their own persistence increment before production deployment.

## Request-to-data path

1. FastAPI receives the request and assigns a request correlation ID.
2. Authentication verifies the session/token and resolves organization, actor, and capabilities.
3. Route dependencies validate path, query, and body types.
4. Application service applies business policy and passes organization scope explicitly to the repository.
5. Repository executes parameterized, bounded queries and returns domain objects.
6. Consequential writes run in a transaction, enforce idempotency, and append an audit event.
7. The response serializer emits only the public contract; internal stack traces and provider payloads stay server-side.

For Sprint 5 analytics, the graph service first applies organization scope and lifecycle lookup, then derives bounded nodes/edges. The pattern service reconciles the organization-scoped lifecycle set and groups stable exception signatures. The evaluation service alone can access hidden labels; its public report contains metrics, never ground-truth records.

## Failure and timeout policy

Database, provider, and external source calls require explicit timeouts. Retries are only allowed for safe, idempotent operations with bounded exponential backoff. Provider failure returns a typed investigation-unavailable state; it never changes reconciliation state or triggers a resolution.

## Deployment stages

| Stage | Web | API | Storage | Evidence required |
| --- | --- | --- | --- | --- |
| Local foundation | Next dev server | optional FastAPI scaffold | in-memory demo adapter | browser smoke check |
| Local P0 | Next dev server | Uvicorn | local PostgreSQL | `fintrace-migrate`, `fintrace-seed`, seed/reconcile/evaluate |
| Staging | Node deployment | containerized API | managed PostgreSQL | migration and security checks |
| Production candidate | immutable build | separately deployable API | encrypted PostgreSQL + backups | load, auth, tenant, recovery tests |
