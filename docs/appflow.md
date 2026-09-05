# FinTrace Application Flow

## Investigation evidence improvement (2026-09-05)

The investigation panel displays the existing deterministic evidence_score as “Evidence confidence / 100,” explicitly not an AI correctness probability. Ambiguous cases compare cited payment records and settlement links, format money using close currency and timestamps in UTC, and group source fields by record in expandable evidence details. Full provider narrative and lookup trace remain available. No financial rules or score calculations change.

Provider recovery: malformed final candidates receive one bounded schema-correction turn; Groq JSON-generation failures receive one compact regeneration. Ambiguous synthesis uses JSON output after mandatory retrieval with up to 12 citations and a 5,000-token response budget. Formatting failures are distinguished from outages. Any FAILED persisted assessment can be retried with a new idempotency key, preserving its identity; same-key replays remain unchanged. The UI exposes retry even after evidence lookups completed.

Open a needs-evidence finding → Investigate evidence → collect scoped candidate evidence → live AI compares records → verify citations → show assessment and what would resolve it. The result shows cited records and keeps lookup details expandable. Legacy results with zero lookups offer “Refresh investigation with source evidence”; this uses a new idempotency key and preserves the investigation identity.

## Operational state semantics (2026-09-03)

Control screens use four explicit states: loading, persisted result, no result yet, and failure. A `404` on a latest-run/latest-evaluation read means the workflow has not run; `403` means the actor lacks the capability; network/5xx failures are retryable service failures. The UI never labels a permission denial as an outage and never replaces an unavailable live provider with a fabricated score. Source mutations require idempotency keys and are safe to retry.

**Version:** 1.0.0  
**Last updated:** 2026-08-31

## Active evolution flow

The primary user journey is investigation-scoped:

```text
Investigations
  → New financial investigation
  → Upload sources (high-confidence setup is automatic)
  → Review only uncertain data links
  → Run close analysis
  → Attention queue and human decisions
  → Patterns, evaluation, audit
```

The `/investigations/*` routes provide the complete local `FinancialInvestigation` close workspace. Its primary stages are **Overview**, **Data**, **Results**, and **Attention**; source files and relationships are details inside Data, while Audit remains secondary. High-confidence source mappings and relationships are prepared automatically, and only uncertainty opens a review action. The current exception detail investigation remains a separate `ExceptionInvestigation` child workflow. The controller-facing outcome vocabulary is `RECONCILED`, `EXPECTED VARIANCE`, `EXPLAINED`, `NEEDS EVIDENCE`, `NEEDS DECISION`, `APPROVAL REQUIRED`, and `FAILED`; internal deterministic exception codes remain unchanged. Ambiguous payment associations are `NEEDS EVIDENCE` when a unique reference is missing, not an invitation for a controller to guess.

### Financial investigation source intake (implemented Sprint 1)

1. Analyst opens **Investigations** and creates a workspace with name, period, and base currency.
2. FinTrace persists the workspace and routes to source intake.
3. Analyst selects one or more CSV/XLSX exports.
4. The API validates format, encoding, headers, size, extracted rows/columns, organization ownership, and idempotency before storing bytes under a generated server reference.
5. The UI refreshes the persisted source list and displays metadata/status. Unsafe or malformed files remain rejected with a safe error.
6. Analyst may remove a source; the API deletes the stored bytes and records an audit event.
7. The Data stage analyzes each file and automatically accepts complete, high-confidence mappings. The compact default view shows file readiness and opens the legacy mapping editor only when a user chooses Review mapping or uncertainty remains. No state implies that reconciliation has run.

### Source analysis and mapping review (implemented Sprint 2 slice)

For an uploaded or generated source, the Data stage requests bounded analysis and displays a compact file-level result. Successful source files are locked against repeat attachment by content and source filename; a same-name source that is still awaiting review or has failed is replaced by the next upload, including cleanup of stale unresolved duplicates. The deterministic alias catalog recognizes common export conventions such as `GatewayTxn`, `SettlementGross`, `NetCredit`, `RefundValue`, `InvoiceNo`, `MovementRef`, and `ActionRef`, so complete required mappings are confirmed automatically. Required-field gaps, unknown columns, and conflicting evidence remain visible and block the close until reviewed; the system never invents a mapping to improve completion metrics. Standard ERP refund exports containing one active and explicit reversed invoice rows are handled deterministically and kept fully accounted for, including employee actions that reference the refund record; ambiguous duplicate active invoices remain a review-blocking condition. Offline analysis is labelled deterministic/offline; a configured live provider is optional and provider failure is shown as unavailable rather than presented as a successful AI result. High-confidence relationships are accepted automatically; only conflicting or ambiguous links expose review actions. Confirmed sources can then be normalized into an immutable dataset version with row-level lineage and reconciled through the deterministic lifecycle engine. Uploaded-run exceptions are investigated from the owning financial investigation; the seeded legacy queue remains a separate compatibility workflow.

## 1. Navigation map

```text
Authenticated workspace
        |
        +--> Home
        |      +--> Current close summary
        |
        +--> Closes
        |      +--> Overview
        |      +--> Data (uploads + uncertain connections)
        |      +--> Results
        |      +--> Attention
        |
        +--> Audit (secondary)
        +--> Evaluation (secondary)
```

## 2. Overview flow

1. User enters the workspace and sees the current reconciliation run.
2. Metric cards answer records processed, auto-reconciled rate, exposure, and review load.
3. Health and throughput show system state without implying live production monitoring.
4. Priority exceptions link to the canonical detail view.
5. Pattern cards show correlation signals and a recommended control.
6. Export report downloads the current investigation summary as a CSV; the investigation control invokes persisted deterministic normalization/reconciliation and reports completion or failure in place. Benchmark evaluation is a separate control under Evaluations.
7. The Results panel separates deterministic explanations from the attention queue. Explained findings show their evidence trail and a follow-up destination where useful; only unresolved evidence gaps, genuine policy decisions, and approval-required actions enter Attention.

Empty state: “No unresolved exceptions. All lifecycles reconciled for this batch.”  
Failure state: “Dashboard unavailable. Try again. Existing run history remains available.”

## 3. Exception queue flow

1. User searches by exception ID, order ID, or exception type.
2. User filters by severity and status.
3. Results show exception, source systems, severity, status, exposure, owner, and age.
4. User selects **Inspect** to open the lifecycle detail.
5. Export queue downloads the currently filtered rows as a CSV; the compact queue filter action opens this screen at the filter controls.
6. No consequential action is performed from the list row; consequential actions are only available on the detail flow and remain policy-gated.

## 4. Exception detail flow

```text
Open exception
      |
      +--> Review deterministic exposure and rules
      +--> Inspect canonical lifecycle records
      +--> View derived lifecycle graph
      +--> Read chronological incident timeline
      +--> Start bounded investigation
               |
               +--> tool calls collected
               +--> structured result validated
               +--> evidence score computed independently
               +--> recommendation displayed
      +--> Request human review
               |
               +--> status becomes IN_REVIEW
               +--> audit event appended
```

The UI must communicate that evidence score is not an AI confidence score and that no resolution is performed by investigation.

## 5. Ambiguity flow

When deterministic matching finds two candidates or contradictory evidence:

```text
AMBIGUOUS
  -> investigation may collect evidence
  -> verifier finds insufficient support
  -> UNRESOLVED
  -> human review required
```

The system must not select a candidate merely to make the dashboard look complete.

For an uploaded reconciliation result, the same safety rule continues through remediation:

```text
duplicate or ambiguous result
  -> bounded evidence investigation
  -> UNRESOLVED
  -> Request human review
  -> approval policy and idempotency checks
  -> APPROVED / REJECTED decision recorded in audit
```

## 6. Role flows

- **Analyst:** view, investigate, annotate, and request review.
- **Finance manager:** all analyst actions plus low-value approval.
- **Controller:** all manager actions plus high-value approval and policy configuration.
- **Auditor:** read-only access to source evidence, investigations, and audit events.

## 7. AI failure flow

```text
Investigation requested
        |
        +--> provider unavailable or invalid result
        |       |
        |       +--> return FAILED / unavailable (HTTP 503 for the uploaded-result route)
        |       +--> show deterministic evidence and the provider-unavailable state
        |       +--> keep human review available
        |       +--> do not change financial state
        |
        +--> evidence is contradictory or insufficient
                |
                +--> return UNRESOLVED
                +--> show ambiguity and human-review state
                +--> keep the controlled review/approval path available
```

## 8. Screen inventory

| Screen | Route | Primary question | Required states |
| --- | --- | --- | --- |
| Overview | `/` | Are books currently reconciled? | populated, empty, unavailable |
| Investigation overview | `/investigations/:id` | What is complete for this period and what is the next close action? | populated, no run, unavailable |
| Data | `/investigations/:id/data` | Are source files ready, and are any relationships uncertain? | ready, needs review, empty, unavailable |
| Reconciliation | `/investigations/:id/reconciliation` | What did the deterministic close analysis prove? | populated, no run, failure |
| Attention queue | `/investigations/:id/attention` | Which items need evidence, a human decision, or approval? | populated, filtered empty, unavailable |
| Exception queue | `/exceptions` | Compatibility-only legacy queue; not part of the primary close navigation. | populated, filtered empty, unavailable |
| Exception detail | `/exceptions/:id` | What happened and what is safe next? | populated, missing ID, investigation unavailable |
| Patterns | `/patterns` | What is recurring? | loading, populated, no patterns, unavailable |
| Runs | `/runs` | What was processed and when? | populated, in progress, failure |
| Evaluations | `/evaluations` | How do we know it works? | loading, populated, never run, failure |
| Audit | `/audit` | Who did what? | loading, populated, no events, unauthorized |
| Settings | `/settings` | What policy is active? | populated, unauthorized |

## 9. Inventory lifecycle evidence

Inventory movements are displayed with sale/return quantity, unit cost, and inventory value when the uploaded export provides them. A full refund without a return is shown as an expected missing inventory step. A return with the wrong quantity or cost value is shown as a mismatch, while inventory restored without a refund is shown as a payment-review exception. These conclusions come from deterministic lifecycle rules; AI may explain the cited records but cannot replace the rule result.
