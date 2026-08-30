# FinTrace Repository Review Protocol

**Purpose:** Make security, architecture, database, and quality reviews repeatable.  
**Mode:** Read-only assessment.  
**Last updated:** 2026-08-30

## 1. Operating rules

The reviewer must discover the stack from the repository and must not ask the author to restate it. The review must not modify source, configuration, migrations, lockfiles, dependencies, or generated artifacts. Do not run auto-fix, formatting-write, migration, seed, deployment, destructive, or production commands. Never print secrets; record only file and variable names with values redacted.

Capture initial Git status and verify final Git status. Respect `AGENTS.md`, contribution instructions, and directory-local rules.

## 2. Review order

If the repository is too large for a complete deep review, create a risk map and inspect in this order:

1. Authentication and authorization.
2. Public APIs and externally controlled inputs.
3. Financial, personal, or sensitive data.
4. File upload and media processing.
5. Database writes and migrations.
6. Administrative functions.
7. Background jobs and integrations.
8. Infrastructure and deployment.
9. Remaining application code.

## 3. Discovery checklist

- Languages and exact runtimes.
- Frameworks, package managers, lockfiles, and dependency versions.
- Every app, service, worker, scheduled job, shared package, and infrastructure component.
- Database technology, schema, migrations, ORM, drivers, indexes, and transaction boundaries.
- API protocol, authentication, authorization, webhooks, and external services.
- Build, lint, format, typecheck, unit, integration, security, dependency, and infrastructure checks.
- Logging, monitoring, error handling, and deployment configuration.

Produce a stack matrix with: component, language/runtime, framework, database/storage, and important configuration.

## 4. Findings standard

Only report material, evidence-backed findings. Every finding includes:

- ID, severity, confidence, category, exact file and line.
- Concrete implementation evidence and actual execution path.
- Realistic trigger or exploit scenario and required attacker capability.
- Business and technical impact.
- Root cause.
- Minimal correction.
- Verification method.
- Relevant CWE, OWASP category, or advisory where applicable.

Do not report a theoretical concern or call a dependency vulnerable without advisory/CVE, affected range, installed version, and reachable impact.

## 5. Required report structure

1. Executive assessment: `BLOCK`, `CONDITIONAL`, or `PASS`; serious risks; insufficient evidence; check status.
2. Technology stack and repository structure.
3. Findings summary table.
4. Detailed findings.
5. Database assessment: integrity, query safety, performance, concurrency, migrations, data protection, runtime limitations.
6. Testing and quality gaps.
7. Remediation plan: P0/P1/P2 with dependencies and smallest safe sequence.
8. Commands executed with exit status and limitations.
9. Coverage and limitations.
10. Final repository state and tracked-file change confirmation.

## 6. FinTrace-specific focus

- Trace tenant authorization from request through service, repository, tool, and final data access.
- Verify money uses decimal-safe types and timestamps are timezone-safe.
- Verify deterministic reconciliation is independent of AI.
- Verify investigator tools cannot mutate data or run arbitrary SQL.
- Verify AI result citations and evidence score independently.
- Verify approval gates, idempotency, audit events, and ambiguous-case escalation.
- Verify AI failure leaves reconciliation and manual review available.
- Verify the UI component boundary: inventory reusable primitives under `packages/ui/src/components`, check public exports/imports, confirm each app `globals.css` is a one-line shared-style import, scan for literal colors, and verify semantic Tailwind token usage.
- Execute `pnpm check:ui-architecture` and record its result alongside `pnpm lint`, `pnpm typecheck`, and `pnpm build`; browser smoke must cover all stable routes at desktop/tablet/mobile widths and representative interaction states.

## 7. Safe command examples

```text
git status --short
rg --files
pnpm typecheck
pnpm lint
pnpm build
python -m pytest
ruff check .
```

Do not install missing tools without explicit permission. If a command cannot run, report the exact reason and do not guess its result.
