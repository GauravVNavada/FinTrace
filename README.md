# FinTrace

FinTrace is a lifecycle-aware financial operations console for investigating exceptions across POS, payments, settlements, ERP, refunds, inventory, and employee activity.

This repository contains the FinTrace close workflow: CSV/XLSX ingestion, automatic high-confidence source mapping, canonical normalization with lineage, deterministic reconciliation, evidence-backed AI investigation, human approval, audit, and PostgreSQL persistence. Groq is the local live-provider configuration; deterministic AI responses are reserved for explicitly labeled automated tests.

## Product boundary

FinTrace follows one core rule: code calculates; AI interprets.

- Deterministic reconciliation owns money, IDs, matching windows, exposure, severity, and approval policy.
- AI is limited to evidence selection, ambiguous exception interpretation, and explanation.
- AI investigation tools are read-only and organization-scoped.
- Human approval is required for consequential actions.
- Synthetic data is used in the sample. No real financial or personal information is included.

## Run locally

Requirements: Node.js 24+, pnpm 9+. Python 3.12+ is required for the API; Docker provides the local PostgreSQL runtime.

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3002` after starting both the API and web service. Follow [`docs/local-development.md`](docs/local-development.md) for database setup and environment configuration. For the validated standalone web server, run `pnpm --filter @fintrace/web build`, then `pnpm --filter @fintrace/web exec next start --port 3002`.

The local sample supports either uploaded synthetic-compatible exports or fresh generated source files. The generator is bounded, reproducible, and passes through the same upload, mapping, normalization, reconciliation, and investigation workflow. All sample records are synthetic; do not use production data in this development setup.

The default API storage backend is the deterministic in-process sample adapter. For the full local path, run `docker compose up -d postgres`, apply `fintrace-migrate`, run `fintrace-seed`, and set `STORAGE_BACKEND=postgres` before starting Uvicorn. The Compose database uses host port `55432` so it does not collide with a local PostgreSQL service. See [`docs/local-development.md`](docs/local-development.md).

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
systhantic data January–August 2026 CSV/XLSX input folders and checksums
e2e            Browser workflow tests
scripts        Development and validation utilities
```

## Documentation map

- [`systhantic data/README.md`](systhantic%20data/README.md) — portable monthly inputs and upload instructions.
- [`docs/release-cleanup.md`](docs/release-cleanup.md) — cleanup scope, compatibility, and validation results.

- [`docs/PRD.md`](docs/PRD.md) — product requirements and scope source of truth.
- [`docs/architecture.md`](docs/architecture.md) — system boundaries, data flow, and deployment shape.
- [`docs/schema.md`](docs/schema.md) — canonical domain model and typed UI contracts.
- [`docs/data-model.md`](docs/data-model.md) — investigation-scoped data ownership and evolution model.
- [`docs/data_api.md`](docs/data_api.md) — API contract and adapter rules.
- [`docs/implementation_plan.md`](docs/implementation_plan.md) — active sprint sequence and delivery protocol.
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
- [`docs/walkthrough.md`](docs/walkthrough.md) — reproducible benchmark and five-minute product walkthrough.

## Release boundary

The local product uses synthetic data, deterministic reconciliation, and simulated approvals. The default live configuration is Gemini `gemini-2.5-flash-lite` with optional Groq fallback `openai/gpt-oss-120b`; set `GEMINI_API_KEY`, `GROQ_API_KEY`, and the runtime provider/model variables in the API environment. Check `/api/v1/ai/provider-health` before a sample: it reports primary and fallback independently without exposing credentials. If unavailable, the API returns an explicit provider failure with a redacted diagnostic category and never labels offline output as AI. Configured models must support strict structured output and tool/function calling. Gemini receives only bounded headers, inferred types, row count, statistics, and representative sample rows for source analysis, and bounded deterministic findings/evidence for investigation. PostgreSQL workflow state, ordered tool traces, fact-level verifier results, provider/fallback diagnostics, and verified bearer claims are implemented. Uploaded-investigation outcomes are scoped to their financial investigation. Evaluation separates deterministic reconciliation metrics from the independently authored AI investigation benchmark. Staging and production configuration fails closed unless a non-default authentication secret and configured external AI provider are supplied; normal tests use the deterministic stub and make zero live provider requests.
