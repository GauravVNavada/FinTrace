# FinTrace Engineering and Product Standards

Status: active · 2026-08-30

## Engineering

- TypeScript strict mode is required.
- Husky pre-commit hooks run the repository lint/typecheck gates; Commitlint enforces Conventional Commits.
- Domain objects are typed and named with controlled enums.
- Components are reusable and data-driven; product data does not live in presentational markup.
- Business rules belong in the backend/domain layer, not React components.
- Every reusable visual component belongs in `packages/ui/src`, with one component per focused file and explicit barrel exports.
- `packages/ui/src/global.css` is the single source for resets, typography, spacing, radii, shadows, semantic color tokens, and theme overrides. App stylesheets may contain only the import of this file.
- Components and app markup use semantic Tailwind/shadcn tokens backed by CSS variables; literal color values, palette utilities such as `bg-slate-900`, and inline color styles are not allowed in reusable components or product screens.
- Shared Tailwind configuration/presets must map semantic utilities to the UI package tokens. Product apps must not redefine the palette.
- All components used by an app must be imported from `packages/ui/src` (directly or through its public barrel); duplicate app-local primitives are prohibited.
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

## Design-system conformance gate

The component boundary is architectural, not cosmetic. A UI change is incomplete until:

- the component exists under `packages/ui/src/<component>.tsx` and is exported from the package entrypoint;
- all supported variants for a primitive live in that primitive's file (for example, every Button variant lives in `button.tsx`);
- the component has no literal color values and uses semantic tokens only;
- the app imports the component from `@fintrace/ui` and does not recreate it locally;
- `apps/*/app/globals.css` contains only the shared stylesheet import;
- `packages/ui/src/global.css` contains the token definitions and theme selectors needed by all apps;
- the component inventory is exercised by at least one route or an explicit component test, and unused duplicate implementations are removed.

## Review checklist

- [ ] PRD and scope still match behavior.
- [ ] Schema/API changes are documented.
- [ ] Tenant and permission implications are considered.
- [ ] Empty, error, loading, and AI-failure paths are safe.
- [ ] Deterministic rules have tests.
- [ ] No secrets or real financial data are present.
- [ ] `pnpm typecheck` and `pnpm build` pass.
