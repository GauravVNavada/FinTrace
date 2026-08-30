# FinTrace Architecture Decisions

## ADR-001 — Turbo monorepo with one web app and one API app

**Status:** Accepted · 2026-08-30

**Decision:** Use pnpm workspaces + Turbo with `apps/web`, `apps/api`, and `packages/ui`.

**Why:** The frontend and backend have different languages and release concerns, but the project is still small enough for one repository and shared documentation. Turbo coordinates JavaScript tasks without imposing rules on the Python service.

**Rejected:** Nx for this increment because the repository does not need Nx generators or a Python plugin; microservices because they would add operational cost without a product need.

## ADR-002 — PostgreSQL as the source of truth

**Decision:** Store canonical financial and operational entities relationally. Derive the event graph in the API response or frontend.

**Why:** Foreign keys, constraints, decimal types, transactions, and audit queries matter more than graph-native traversal for this MVP.

## ADR-003 — Deterministic reconciliation before AI

**Decision:** Matching, money, exposure, severity, and authorization remain code-owned.

**Why:** These decisions need reproducibility, explainability, and safe failure. AI is reserved for interpreting heterogeneous evidence after a deterministic exception exists.

## ADR-004 — Typed demo adapter before persistence

**Decision:** The initial UI uses a typed in-memory adapter while the API and database are being established.

## ADR-005 — Repository-backed workflow durability

**Status:** Accepted · 2026-08-30

**Context:** Investigations, evaluation reports, approval controls, and idempotency responses must survive API process restarts and remain organization-scoped.

**Decision:** Extend the repository boundary with durable workflow operations. PostgreSQL stores validated response snapshots in JSONB alongside normalized foreign keys and ordered tool calls; the demo repository implements the same contract in process for unit/API tests. A request hash is checked before replaying any stored idempotent response.

**Consequences:** Services remain independent of SQL and financial calculations remain deterministic. JSONB is a response projection, not a replacement for canonical financial tables. Cross-process approval safety is enforced with organization-scoped foreign keys, row locks, and unique actor/request constraints.

## ADR-006 — Signed claims with explicit development fallback

**Status:** Accepted · 2026-08-30

**Context:** Local browser smoke tests need a low-friction tenant context, while deployment must not trust browser-supplied organization or role headers.

**Decision:** Verify HS256 bearer claims in the API when present and require them when `AUTH_MODE=required`. Header context is available only in explicit development mode. Claims must include subject, organization, role, issuer, audience, issued-at, and expiry.

**Consequences:** The local demo remains easy to run, while deployment has an explicit fail-closed switch. Production still needs managed key rotation, revocation, rate limiting, and an identity provider integration.

**Why:** This keeps the product flow reviewable and the frontend contracts concrete without pretending persistence or provider integration exists. The adapter is replaceable through the API contract.

## ADR-005 — No arbitrary AI tools

**Decision:** Evidence access uses named, parameterized, read-only tools.

**Why:** Direct SQL or arbitrary code execution would make tenant isolation, prompt injection, and auditability harder to prove.

## ADR-006 — Centralized shadcn component and token boundary

**Status:** Accepted; implemented for the current web surface · 2026-08-30

**Decision:** All reusable UI components live in `packages/ui/src/components`; global design infrastructure remains directly under `packages/ui/src`. Each primitive has a focused file, all of its variants remain in that file, and the package barrel is the only public import surface. `packages/ui/src/global.css` is the single global stylesheet. Every app stylesheet contains only one import of it.

Components consume semantic Tailwind utilities backed by CSS variables. Literal colors, palette utilities, inline color styles, duplicate app-local primitives, and product-specific styling inside the shared package are prohibited. Multiple apps use namespaced theme selectors in the shared token file rather than separate token implementations.

**Why:** This gives the repository one accessible, testable design system, prevents visual drift, makes themes explicit, and keeps product applications focused on composition and behavior.

**Acceptance evidence:** `docs/ui_component_inventory.md`, focused primitive files, public exports, semantic Tailwind preset, stylesheet line-count check, literal-color scan, duplicate-control scan, production build, and route/component smoke tests. The inventory is complete for the current web surface; future primitives must follow the change procedure in that document.
