# FinTrace Operations and Observability

## Final local validation — 2026-09-05

See [final-validation.md](final-validation.md) for tested behavior and explicit remaining production limitations. Inventory investigations precollect bounded read-only evidence and allow one verification-correction turn, never bypassing the verifier. Failed verification remains unresolved and can be retried with a new idempotency key. Uploaded lifecycle reads are authenticated tenant/run/result scoped. Development authentication remains local-demo-only; no financial execution integration is implied.

**Status:** local product operational contract; ingestion, reconciliation, replay recovery, and bounded audit observability defined · 2026-09-03

## Ingestion metrics

The evolution pipeline must expose safe counts and durations for generation, upload, analysis, mapping, normalization, lifecycle construction, reconciliation, and investigation. Logs may contain investigation/source/run IDs, statuses, sizes, row counts, and durations, but never file contents, provider prompts, tokens, or raw personal/financial payloads.

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

The API middleware generates or validates a bounded `X-Request-Id`, returns it on every response, logs method/path/status/duration, and makes it available to audit correlation. Logs contain event names, status, duration, and safe identifiers. They do not contain tokens, full source records, prompts, model payloads, or personal data.

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

## Console state semantics (2026-09-03)

The web console treats `/ready` as process/dependency connectivity only. A missing latest evaluation is a normal not-yet-run state; authorization failures and dependency failures remain distinct and expose a retry or access action. This prevents an operationally healthy API from being represented as a red outage merely because there is no result yet.
