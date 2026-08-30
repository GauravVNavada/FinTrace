# FinTrace Application Flow

**Version:** 1.0.0  
**Last updated:** 2026-08-30

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

Empty state: “No unresolved exceptions. All lifecycles reconciled for this batch.”  
Failure state: “Dashboard unavailable. Try again. Existing run history remains available.”

## 3. Exception queue flow

1. User searches by exception ID, order ID, or exception type.
2. User filters by severity and status.
3. Results show exception, source systems, severity, status, exposure, owner, and age.
4. User selects **Inspect** to open the lifecycle detail.
5. No action is performed from the list row; consequential actions are only available on the detail flow and remain policy-gated.

## 4. Exception detail flow

```text
Open exception
      |
      +--> Review deterministic exposure and rules
      +--> Inspect canonical lifecycle records
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
                |
                +--> show deterministic evidence
                +--> mark investigation unavailable
                +--> keep review request available
                +--> do not change financial state
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
