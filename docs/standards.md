# FinTrace Engineering and Product Standards

Status: active · 2026-08-30

## Engineering

- TypeScript strict mode is required.
- Husky pre-commit hooks run the repository lint/typecheck gates; Commitlint enforces Conventional Commits.
- Domain objects are typed and named with controlled enums.
- Components are reusable and data-driven; product data does not live in presentational markup.
- Business rules belong in the backend/domain layer, not React components.
- Shared visual primitives belong in `packages/ui`.
- Every new route needs a useful loading, empty, and error state before it is considered complete.
- Consequential operations are idempotent and auditable.

## Financial correctness

- Normalize money in integer minor units or decimal-safe types; never binary floating point for accounting.
- Deterministic code owns matching, exposure, severity, approval thresholds, and status.
- AI cannot approve, move money, or directly update source systems.
- `UNKNOWN` and `AMBIGUOUS` are valid outcomes.
- Tests accompany every financial rule and scenario.

## Security and privacy

- Tenant scope is enforced by authenticated server context on every business query.
- Frontend hiding is not authorization.
- Secrets are environment variables and never committed.
- Tool calls are allowlisted, read-only, validated, rate bounded, and logged.
- Synthetic data is the only data in this repository.
- Audit history is append-only at the application level.

## UX

- The product should feel like a serious operations console, not a chatbot.
- Use dense but readable tables, timelines, evidence, clear numbers, and restrained AI presentation.
- Red means high-risk unresolved work; amber means review/pending; green means reconciled/resolved; neutral means information.
- Avoid giant chat surfaces, gradients, fake live alerts, and unsupported “AI confidence” claims.
- Always show what is known, what is missing, and what action is gated.

## Documentation change rule

Any change to requirements, scope, schema, API, architecture, agent behavior, or safety policy must update the relevant Markdown file in `docs/` in the same change. If product behavior changes, update `docs/PRD.md` first and record the implementation consequence in the relevant supporting document.

## Review checklist

- [ ] PRD and scope still match behavior.
- [ ] Schema/API changes are documented.
- [ ] Tenant and permission implications are considered.
- [ ] Empty, error, loading, and AI-failure paths are safe.
- [ ] Deterministic rules have tests.
- [ ] No secrets or real financial data are present.
- [ ] `pnpm typecheck` and `pnpm build` pass.
