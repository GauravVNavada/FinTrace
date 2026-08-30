# FinTrace Repository Instructions

## Source of truth

Read `docs/PRD.md` first for product intent. Keep `docs/requirements.md`, `docs/appflow.md`, `docs/architecture.md`, `docs/schema.md`, `docs/data_api.md`, `docs/phase_scope.md`, `docs/agents.md`, and the operational/security documents synchronized with implementation.

## Change discipline

- Do not silently change product scope.
- A user-visible behavior change updates the PRD and the relevant requirement/flow/scope document in the same change.
- A schema or endpoint change updates `docs/schema.md` and `docs/data_api.md` before implementation is considered complete.
- Keep `apps/web` presentation-focused; keep business rules in `apps/api`/domain services.
- Keep shared UI primitives in `packages/ui` and do not put product data there.

## Safety and quality

- Deterministic code owns money, matching, exposure, severity, authorization, and approval.
- AI only interprets bounded, cited evidence and cannot mutate financial state.
- Tenant scope is mandatory at the API/repository/tool boundary.
- Use decimal-safe monetary arithmetic and timezone-aware timestamps.
- Consequential writes require idempotency and audit events.
- Ambiguity is a first-class outcome; never guess to improve metrics.

## Review mode

For repository audits, follow `docs/review_protocol.md`. Audits are read-only and must not auto-fix, install dependencies, run migrations/seeds, or modify the repository.
