# FinTrace Requirements Specification

**Version:** 1.0.0  
**Status:** Active  
**Last updated:** 2026-08-31
**Source:** [`PRD.md`](PRD.md)

## 1. Purpose

This document converts the product narrative into testable system requirements. The PRD remains the authority for product intent; this file is the implementation checklist for acceptance criteria, failure behavior, and non-functional expectations.

## 2. Actors and capabilities

| Actor | Read | Investigate | Request review | Approve | Configure policy | Audit read |
| --- | --- | --- | --- | --- | --- | --- |
| Analyst | Dashboard, exceptions, evidence | Yes | Yes | No | No | No |
| Finance manager | All analyst access | Yes | Yes | Low-value | No | Yes |
| Controller | All manager access | Yes | Yes | High-value | Yes | Yes |
| Auditor | Read-only evidence and history | No | No | No | No | Yes |

Authorization is enforced in the API. UI visibility is not evidence of authorization.

## 3. Functional requirements

### FIN — Financial investigation ingestion evolution

| ID | Requirement | Status / acceptance criteria |
| --- | --- | --- |
| FIN-001 | Create a financial investigation workspace | Complete Sprint 1; persists organization, period, currency, creator, status, and timestamps. |
| FIN-002 | Upload supported source files | Complete Sprint 1; accepts CSV/XLSX only, validates type/size/content, stores safe metadata, and never trusts a browser path. |
| FIN-003 | Preserve source lineage | Implemented Sprint 3; normalized records retain source file, row, column, and source-record references. |
| FIN-004 | Keep domain terms distinct | Active; financial workspace, exception investigation, reconciliation run, and evaluation run have separate identifiers and lifecycles. |
| FIN-005 | Require explicit mapping confirmation | Implemented Sprint 2 slice; web review, allowlisted edits, and unresolved-required-field blocking are active before normalization. |
| FIN-006 | Keep ambiguity first-class | Active; uncertain relationships become `AMBIGUOUS`/`UNRESOLVED` and are never guessed. |
| FIN-007 | Analyze bounded source structure | Active Sprint 2; only headers, inferred column profiles, bounded samples, and row/column counts are analyzed. |
| FIN-008 | Produce reviewable source classification | Active Sprint 2; deterministic offline classification is available and an explicitly configured provider may propose a classification; provider status is persisted. |
| FIN-009 | Persist mapping proposals and edits | Active Sprint 2; proposals are tenant-scoped, canonical fields are allowlisted, and confirmed mappings cannot be edited in place. |
| FIN-010 | Record source-analysis outcomes | Active Sprint 2; analysis, mapping, confirmation, edit, and provider-failure events are auditable and safe to inspect. |
| FIN-011 | Discover relationships deterministically | Implemented Sprint 3 slice; proposals use confirmed canonical join fields, remain tenant-scoped, and require explicit acceptance, rejection, or edit decision. |
| FIN-012 | Refuse unjoinable normalized data | Implemented Sprint 3 hardening; unsupported source types and rows without a canonical relationship key block lifecycle construction instead of being silently discarded. |
| FIN-013 | Expose investigation-scoped outcomes | Implemented Sprint 4–6 slice; persisted run metrics, results, advisory patterns, and uploaded exception investigation traces are retrieved only through the owning financial investigation and organization scope. |
| FIN-014 | Generate fresh synthetic source exports | Implemented Sprint 7; bounded `orders`, `seed`, `anomaly_rate`, and allowlisted scenario selection create source files through the same upload pipeline, require idempotency, and refuse overwrite when sources already exist. |
| FIN-015 | Route uploaded outcomes into controlled review | Uploaded `EXCEPTION` and `AMBIGUOUS` results expose an idempotent, organization-scoped review-request path that reuses server-side action and approval policy. |

### RECON — Reconciliation

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| RECON-001 | Process a reproducible synthetic batch | Seed and record count are configurable; seed 42 produces the demo batch. |
| RECON-002 | Normalize source records | Implemented Sprint 3 slice; decimal monetary fields become integer minor units, timestamps and source references are validated, malformed/duplicate records block the dataset, and unknown/unjoinable rows are refused. |
| RECON-003 | Reconcile deterministically | Exact IDs, references, amount consistency, fees, taxes, and timing windows are evaluated without an LLM. |
| RECON-004 | Assign one lifecycle status | Each lifecycle is `RECONCILED`, `RECONCILED_WITH_VARIANCE`, `EXCEPTION`, `AMBIGUOUS`, or `PENDING`. |
| RECON-005 | Preserve ground truth isolation | The investigator cannot access `ground_truth.json`; only evaluation code can. |
| RECON-006 | Query a canonical lifecycle | A tenant-scoped order lookup returns all related source records or a safe not-found response. |
| RECON-007 | Produce reproducible evaluation metrics | A seeded run reports match rate, precision/recall, throughput, and unresolved cases without AI. |
| RECON-008 | Keep investigation metrics API-backed | Implemented Sprint 4; investigation overview, runs, patterns, and source/detail surfaces read persisted API results and expose honest loading, empty, and unavailable states without fixture substitution. |

### EXC — Exceptions

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| EXC-001 | Detect meaningful exception types | MVP covers at least six required types and includes ambiguous cases. |
| EXC-002 | Compute exposure in code | Exposure is reproducible and never generated by the model. |
| EXC-003 | Prioritize deterministically | Severity is derived from type, exposure, and recurrence policy. |
| EXC-004 | Show complete evidence | Detail view exposes source records, lifecycle state, findings, and missing evidence. |
| EXC-005 | Preserve uncertainty | Ambiguous or insufficient evidence becomes `UNRESOLVED` and requires review. |

### INV — Investigation

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| INV-001 | Use bounded tools | The configured provider may select only from allowlisted, read-only, organization-scoped tools; the service validates and caps every plan. |
| INV-002 | Validate structured output | Schema validation occurs before display or persistence; retry once, then fail safely. |
| INV-003 | Verify citations | Cited records exist, belong to the tenant, and support the root-cause code. |
| INV-004 | Recommend only controlled actions | Free-text actions are not executable; action codes are allowlisted. |
| INV-005 | Audit the investigation | Investigation start, tool calls, result validation, and review request are logged. |
| INV-006 | Fail safely when the provider is unavailable | The API retries explicit provider key pools only for bounded transient failures, can continue the same conversation/tool state through an explicitly configured fallback, and returns a typed failed investigation otherwise; deterministic evidence remains accessible and no resolution or source-system mutation occurs. |
| INV-007 | Retrieve a validated investigation trace | Implemented Sprint 5 slice; a tenant-scoped run/result route returns the persisted status, deterministic evidence score, citations, review requirement, and ordered read-only tool calls. |

### SAFE — Safety and controls

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| SAFE-001 | Require approval for consequential actions | Amount thresholds and exception rules are evaluated server-side. |
| SAFE-002 | Never move real money in MVP | Resolution is simulated and produces an audit event only. |
| SAFE-003 | Prevent cross-tenant access | Every business query receives authenticated organization context. |
| SAFE-004 | Keep finance available if AI fails | Deterministic reconciliation and manual review remain usable. |
| SAFE-005 | Make retry-safe writes | Reconciliation, uploaded-exception investigation, and resolution writes require idempotency keys and replay stable responses. |
| SAFE-006 | Enforce capability-level approval | Approval and rejection are authorized against server-side capability and threshold policy, not UI role visibility. |
| SAFE-007 | Prevent duplicate approval effects | Same-key replay is stable, different request reuse conflicts, and concurrent duplicate decisions are rejected. |

## 4. Non-functional requirements

- **Security:** No secrets in source; API input validation; tenant isolation; server-side authorization; safe error envelope.
- **Reliability:** Deterministic calculations; bounded timeouts; conservative transient-only failover; no action on provider failure; append-only audit events.
- **Performance:** Dashboard reads should be aggregate-backed; reconciliation throughput is measured separately from AI latency; exception lists are paginated in the API.
- **Accessibility:** Keyboard-visible focus, semantic headings, accessible contrast, status labels not conveyed by color alone, and useful empty/error states.
- **Observability:** Correlate request, organization, run, exception, and investigation IDs without logging sensitive payloads.
- **Maintainability:** Strict types, narrow modules, documented decisions, and tests for critical domain rules.

### UI — Design-system requirements

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| UI-001 | Centralize reusable components | Every reusable component used by an app exists under `packages/ui/src/components`, is exported publicly, and is imported by the app from `@fintrace/ui`. |
| UI-002 | Keep primitive variants together | Each primitive file contains all supported variants, sizes, and states for that primitive; app code does not fork variants. |
| UI-003 | Centralize global styling | `packages/ui/src/global.css` owns reset, typography, semantic tokens, themes, and shared global utilities; each app `globals.css` contains exactly one import and no declarations. |
| UI-004 | Prohibit hardcoded colors | Components and app markup contain no literal color values, palette utility classes, or inline color styles; Tailwind utilities resolve through semantic CSS variables. |
| UI-005 | Support multi-app themes | Theme differences are represented by namespaced selectors/tokens in the shared global stylesheet; apps select a theme without defining a second palette. |
| UI-006 | Verify component usage | The component inventory has no unused duplicate primitives, every exported primitive is either route-used or covered by an explicit component test, and static import/style scans are part of the quality gate. |
| UI-007 | Make visible controls actionable | Export controls download the current scoped data, run controls call the bounded idempotent evaluation contract, navigation/filter controls reach the relevant screen/state, and informational controls expose an honest local state rather than silently doing nothing. |

Current evidence for UI-001 through UI-006 is maintained in [`ui_component_inventory.md`](ui_component_inventory.md) and enforced by `pnpm check:ui-architecture`.

## 5. Acceptance scenarios

1. Clean sale with fee variance is reconciled with variance and zero loss exposure.
2. Captured payment without settlement becomes an exception after the timing window.
3. Refund without inventory return becomes high severity with exposure and review required.
4. Two valid payment candidates become ambiguous; the system does not guess.
5. AI provider failure leaves deterministic evidence and manual review available.
6. Repeated resolution request with the same idempotency key creates one workflow effect.
7. Analyst and Finance Manager cannot approve a high-value request; an authorized Controller can approve it exactly once.
8. Export actions produce a CSV of the current screen's scoped data; run/evaluation actions report their API result and disable duplicate submissions while pending.

## 6. Traceability

Requirements map to PRD sections 7–12, 19–40, 46–67, 80–86, and 91–114. Test cases and implementation status are tracked in [`testing.md`](testing.md) and [`phase_scope.md`](phase_scope.md).
