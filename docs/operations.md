# FinTrace Operations and Observability

**Status:** MVP operational contract · 2026-08-30

## Correlation fields

Every API request and domain workflow should carry:

```text
request_id
organization_id
reconciliation_run_id
exception_id
investigation_id
idempotency_key
```

Logs contain event names, status, duration, and safe identifiers. They do not contain tokens, full source records, prompts, model payloads, or personal data.

## Health endpoints

- `/health` — process-level health; must not claim database health unless it performs a bounded dependency check.
- `/api/v1/dashboard/summary` — business read used to detect aggregate freshness.

Readiness and liveness should be separate before production. Dependency checks need timeouts and must not cause retry storms.

## Metrics

### Reconciliation

- lifecycles processed;
- records per second;
- matched, variance, exception, ambiguous, pending counts;
- match precision and recall against hidden ground truth.

### Investigation

- investigations requested/completed/failed;
- p50/p95 duration;
- tool-call count and latency;
- verifier rejection count;
- unresolved rate;
- provider error rate and cost when available.

### Safety

- approval requests by role and value;
- rejected unauthorized attempts;
- idempotency replays;
- unsafe resolution count (target zero);
- cross-tenant access denials.

## Alerting

Alert on sustained provider failures, database errors, high unresolved growth, unsafe-resolution count above zero, queue age, and audit write failures. Do not alert on a single expected ambiguous case.

## Incident response

1. Preserve correlation IDs and current audit events.
2. Disable AI investigation via feature flag if the provider is unsafe or unavailable.
3. Keep deterministic reconciliation and manual review available.
4. Do not replay consequential writes without idempotency verification.
5. Record root cause, affected organization scope, and recovery evidence.
