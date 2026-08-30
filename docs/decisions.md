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

**Why:** This keeps the product flow reviewable and the frontend contracts concrete without pretending persistence or provider integration exists. The adapter is replaceable through the API contract.

## ADR-005 — No arbitrary AI tools

**Decision:** Evidence access uses named, parameterized, read-only tools.

**Why:** Direct SQL or arbitrary code execution would make tenant isolation, prompt injection, and auditability harder to prove.
