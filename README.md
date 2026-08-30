# FinTrace

FinTrace is a lifecycle-aware financial operations console for investigating exceptions across POS, payments, settlements, ERP, refunds, inventory, and employee activity.

This repository contains the FinTrace MVP: a polished web experience and FastAPI service boundary. Dashboard summary, exception queue/detail, investigations, patterns, evaluations, and audit activity use typed API clients; the runs/settings surfaces remain intentionally read-only configuration views. PostgreSQL mode provides durable workflow persistence, while the deterministic demo adapter remains available for isolated tests.

## Product boundary

FinTrace follows one core rule: code calculates; AI interprets.

- Deterministic reconciliation owns money, IDs, matching windows, exposure, severity, and approval policy.
- AI is limited to evidence selection, ambiguous exception interpretation, and explanation.
- AI investigation tools are read-only and organization-scoped.
- Human approval is required for consequential actions.
- Synthetic data is used in the demo. No real financial or personal information is included.

## Run locally

Requirements: Node.js 24+, pnpm 9+. Python 3.12+ is required for the API; Docker provides the local PostgreSQL runtime.

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

The default API storage backend is the deterministic in-process demo adapter. For the full local path, run `docker compose up -d postgres`, apply `fintrace-migrate`, run `fintrace-seed`, and set `STORAGE_BACKEND=postgres` before starting Uvicorn. The Compose database uses host port `55432` so it does not collide with a local PostgreSQL service. See [`docs/local-development.md`](docs/local-development.md).

Validation commands:

```bash
pnpm typecheck
pnpm build
```

## Git quality gates

Husky is configured for local commit safeguards:

- `pre-commit` runs the repository lint and typecheck gates before a commit.
- `commit-msg` enforces Conventional Commits through Commitlint.
- Hooks are installed automatically by the root `prepare` script after dependency installation.

Use commit messages such as `feat: add exception investigation flow` or `fix: guard ambiguous payment matches`.

## Repository

```text
apps/web       Next.js application and product experience
apps/api       FastAPI service boundary and typed API schemas
packages/ui    Shared shadcn-style primitives
docs           Source-of-truth product and engineering documentation
```

## Documentation map

- [`docs/PRD.md`](docs/PRD.md) — product requirements and scope source of truth.
- [`docs/architecture.md`](docs/architecture.md) — system boundaries, data flow, and deployment shape.
- [`docs/schema.md`](docs/schema.md) — canonical domain model and typed UI contracts.
- [`docs/data_api.md`](docs/data_api.md) — API contract and adapter rules.
- [`docs/phase_scope.md`](docs/phase_scope.md) — phase gates and definition of done.
- [`docs/agents.md`](docs/agents.md) — bounded AI responsibilities and safety rules.
- [`docs/standards.md`](docs/standards.md) — engineering, UX, security, and documentation standards.
- [`docs/requirements.md`](docs/requirements.md) — traceable functional and non-functional requirements.
- [`docs/appflow.md`](docs/appflow.md) — screen-by-screen journeys, states, and role flows.
- [`docs/security.md`](docs/security.md) — threat model and security controls.
- [`docs/testing.md`](docs/testing.md) — unit, integration, frontend, and AI regression strategy.
- [`docs/evaluation.md`](docs/evaluation.md) — deterministic benchmark methodology and metric definitions.
- [`docs/operations.md`](docs/operations.md) — observability, metrics, alerts, and incident response.
- [`docs/decisions.md`](docs/decisions.md) — architecture decision records.
- [`docs/local-development.md`](docs/local-development.md) — local setup for web and API.
- [`docs/review_protocol.md`](docs/review_protocol.md) — read-only audit protocol for repository reviews.
- [`docs/demo_script.md`](docs/demo_script.md) — reproducible benchmark and five-minute product walkthrough.

## Release boundary

The MVP uses synthetic data, deterministic reconciliation, a safe stub provider, and simulated approvals. PostgreSQL workflow state and verified bearer claims are implemented. Production still needs deployment-grade identity/key rotation, rate limiting, CSP/HSTS, managed backups, dependency auditing, secret scanning, and a configured external AI provider if AI-assisted interpretation is desired.
