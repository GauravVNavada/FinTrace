# FinTrace Application Flow

**Version:** 1.0.0  
**Last updated:** 2026-08-31

## Active evolution flow

The existing navigation remains available for the seeded MVP. The new primary user journey will be investigation-scoped:

```text
Investigations
  → New financial investigation
  → Upload sources
  → Review mappings
  → Review relationships
  → Build dataset/lifecycles
  → Reconcile
  → Exceptions, patterns, evaluation, audit
```

The `/investigations/*` routes provide the complete local `FinancialInvestigation` workspace and source-to-reconciliation flow. Sources can be uploaded or generated fresh; the current exception detail investigation remains a separate `ExceptionInvestigation` child workflow.

### Financial investigation source intake (implemented Sprint 1)

1. Analyst opens **Investigations** and creates a workspace with name, period, and base currency.
2. FinTrace persists the workspace and routes to source intake.
3. Analyst selects one or more CSV/XLSX exports.
4. The API validates format, encoding, headers, size, extracted rows/columns, organization ownership, and idempotency before storing bytes under a generated server reference.
5. The UI refreshes the persisted source list and displays metadata/status. Unsafe or malformed files remain rejected with a safe error.
6. Analyst may remove a source; the API deletes the stored bytes and records an audit event.
7. The source page can analyze each file, review/edit mappings, and confirm required fields. It also offers bounded fresh synthetic generation only before sources exist. No state implies that reconciliation has run.

### Source analysis and mapping review (implemented Sprint 2 slice)

For an uploaded or generated source, the web flow can request bounded analysis, review classification and mapping proposals, edit or ignore columns, and explicitly confirm mappings. Required-field gaps remain visible and block confirmation. Offline analysis is labelled deterministic/offline; a configured live provider is optional and provider failure is shown as unavailable rather than presented as a successful AI result. The investigation overview and standalone relationship route can discover deterministic relationship proposals and accept or reject them; confirmed sources can then be normalized into an immutable dataset version with row-level lineage and reconciled through the deterministic lifecycle engine. Uploaded-run exceptions are investigated from the owning financial investigation; the seeded legacy queue remains a separate compatibility workflow.

## 1. Navigation map

```text
Authenticated workspace
        |
        +--> Overview
        |      +--> Reconciliation health
        |      +--> Priority exceptions
        |      +--> Recurring patterns
        |
        +--> Exceptions
        |      +--> Filters/search
        |      +--> Exception detail
        |             +--> Lifecycle
        |             +--> Timeline
        |             +--> Evidence investigation
        |             +--> Approval guardrail
        |             +--> Audit history
        |
        +--> Patterns
        +--> Reconciliation runs
        +--> Evaluations
        +--> Audit trail
        +--> Settings
```

## 2. Overview flow

1. User enters the workspace and sees the current reconciliation run.
2. Metric cards answer records processed, auto-reconciled rate, exposure, and review load.
3. Health and throughput show system state without implying live production monitoring.
4. Priority exceptions link to the canonical detail view.
5. Pattern cards show correlation signals and a recommended control.
6. Export report downloads the current investigation summary as a CSV; the investigation control invokes persisted deterministic normalization/reconciliation and reports completion or failure in place. Benchmark evaluation is a separate control under Evaluations.

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
| Exception queue | `/exceptions` | What needs attention? | populated, filtered empty, unavailable |
| Exception detail | `/exceptions/:id` | What happened and what is safe next? | populated, missing ID, investigation unavailable |
| Patterns | `/patterns` | What is recurring? | loading, populated, no patterns, unavailable |
| Runs | `/runs` | What was processed and when? | populated, in progress, failure |
| Evaluations | `/evaluations` | How do we know it works? | loading, populated, never run, failure |
| Audit | `/audit` | Who did what? | loading, populated, no events, unauthorized |
| Settings | `/settings` | What policy is active? | populated, unauthorized |
