# FinTrace Data and API Contract

Status: MVP contract draft; PostgreSQL repository path added · 2026-08-30

## Adapter rule

The web application uses typed API clients for patterns, evaluations, and audit activity. The overview, exception, and run surfaces still retain the typed demo adapter until the corresponding backend read routes are complete. Components may consume domain objects from an adapter, but may not duplicate records or implement data normalization. Replacing a remaining adapter call with an API call should not require changing the UI component contracts.

## API envelope

Successful responses return a resource or collection. Errors use a stable envelope and never expose stack traces:

```json
{
  "error": {
    "code": "EXCEPTION_NOT_FOUND",
    "message": "Exception does not exist.",
    "request_id": "req_01J..."
  }
}
```

## Versioned endpoints

### `GET /ready`

**Auth:** none for local process checks.  
**Behavior:** returns `ready` for the demo backend; when `STORAGE_BACKEND=postgres`, performs a bounded database connectivity check and returns `503` if the database is unavailable. This endpoint does not run migrations.

```text
POST /api/v1/reconciliation-runs
GET  /api/v1/reconciliation-runs
GET  /api/v1/reconciliation-runs/{id}

GET  /api/v1/dashboard/summary
GET  /api/v1/dashboard/trends

GET  /api/v1/exceptions
GET  /api/v1/exceptions/{id}
GET  /api/v1/exceptions/{id}/timeline
GET  /api/v1/exceptions/{id}/graph
GET  /api/v1/lifecycles/{order_id}

POST /api/v1/exceptions/{id}/investigations
GET  /api/v1/investigations/{id}
GET  /api/v1/investigations/{id}/tool-calls

GET  /api/v1/exceptions/{id}/recommendation
POST /api/v1/exceptions/{id}/resolution-request
POST /api/v1/approvals/{id}/approve
POST /api/v1/approvals/{id}/reject

GET  /api/v1/audit-events

GET  /api/v1/patterns
GET  /api/v1/patterns/{id}
POST /api/v1/evaluation/run
GET  /api/v1/evaluation/latest
```

## Request requirements

- `organization_id` comes from authenticated server context; it is never trusted from a browser body.
- Consequential POST requests require `Idempotency-Key`.
- All query filters are validated against allowlisted enum values.
- Pagination is cursor-based before production scale.
- Every response carries or logs a `request_id`.

## Investigation contract

The server sends exception metadata and tool definitions to the provider. It does not send every table. Each tool returns structured JSON and is scoped to the authenticated organization. The server validates the model result, verifies evidence existence and support, and computes the evidence score. The current demo adapter keeps the investigation result in process memory; persistence and tool-call audit events are implemented in the persistence/audit sprint.

## Caching and freshness

Dashboard aggregates may be cached by reconciliation run ID. Exception detail and audit history should be read fresh. No source record should be cached across organization scopes.

## Data migration rule

When persistence is introduced, create an explicit migration for each schema change. Do not mutate tables at application startup. Update [`docs/schema.md`](schema.md) and the PRD in the same pull request.

## Endpoint specifications

### `POST /api/v1/reconciliation-runs`

**Auth:** `reconciliation.run`  
**Headers:** `Idempotency-Key` required.  
**Behavior:** starts a deterministic run against an approved input batch. It never calls the AI provider. The response identifies the run and exposes progress/status; the completed run contains aggregate metrics and exception counts.  
**Failure:** `INVALID_DATASET`, `RUN_ALREADY_EXISTS`, `IDEMPOTENCY_CONFLICT`.

### `GET /api/v1/reconciliation-runs/{id}`

**Auth:** `dashboard.read`  
**Response:** run metadata, counts by reconciliation status, throughput, and evaluation metrics when ground truth is available to the evaluator. Ground truth is never included in a normal API response.

### `GET /api/v1/dashboard/summary`

**Auth:** `dashboard.read`  
**Query:** `run_id` optional; defaults to the latest completed run.  
**Response:** lifecycle count, auto-reconciled count, exception count, exposure, review count, run metadata.  
**Failure:** `RUN_NOT_FOUND`, `AGGREGATE_UNAVAILABLE`.

### `GET /api/v1/exceptions`

**Auth:** `exception.read`  
**Query:** `status`, `severity`, `type`, `assignee`, `cursor`, `limit` (maximum 100), and `q` (maximum 100 characters).  
**Ordering:** severity rank, then `detected_at DESC`.  
**Response:** `{ data: ExceptionSummary[], page: { next_cursor, has_more } }`.  
**Failure:** `INVALID_FILTER`, `TENANT_CONTEXT_REQUIRED`.

### `GET /api/v1/exceptions/{id}`

**Auth:** `exception.read`  
**Response:** exception metadata, exposure, deterministic rule findings, lifecycle records, timeline, policy state, and links to investigation/audit resources.  
**Authorization:** object-level organization ownership is checked before lookup result is returned. A cross-tenant ID returns the same not-found shape as an unknown ID.

### `GET /api/v1/lifecycles/{order_id}`

**Auth:** `exception.read`  
**Response:** canonical order, payments, settlements, invoices, refunds, inventory movements, and employee actions for one order.  
**Authorization:** the authenticated organization is applied to every related read; unknown and cross-tenant lifecycles return the same `RESOURCE_NOT_FOUND` shape.  
**Current implementation:** the development adapter reads the deterministic seed-42 dataset. The PostgreSQL repository replaces it in the persistence sprint.

### `POST /api/v1/exceptions/{id}/investigations`

**Auth:** `exception.investigate`  
**Headers:** `Idempotency-Key` required.  
**Behavior:** collects bounded read-only evidence and returns a structured investigation result. It does not approve or resolve.  
**Failure:** `EXCEPTION_NOT_FOUND`, `INVESTIGATION_IN_PROGRESS`, `PROVIDER_UNAVAILABLE` (503 with a safe failed result), `RESULT_REJECTED` (unresolved result requiring review).

**Current demo:** `EXC-1042` in `ORG-001` is the deterministic flagship fixture. It cites the refund, active invoice, payment, order, inventory, and employee-action evidence without exposing source-system mutation or a provider score.

### `POST /api/v1/exceptions/{id}/resolution-request`

**Auth:** `resolution.request`  
**Headers:** `Idempotency-Key` required.  
**Behavior:** creates one approval request if policy requires it; otherwise returns a simulated safe action only where explicitly allowlisted.  
**Failure:** `ACTION_NOT_ALLOWED`, `APPROVAL_REQUIRED`, `INVALID_STATE`, `IDEMPOTENCY_CONFLICT`.

**Current demo:** resolution and approval state is held by an in-process controls service. Development actor headers (`X-Actor-Id`, `X-Actor-Role`) are test-only context and must be replaced with verified identity claims before deployment.

### `POST /api/v1/approvals/{id}/approve`

**Auth:** `resolution.approve.low` or `resolution.approve.high` depending on policy.  
**Headers:** `Idempotency-Key` required.  
**Behavior:** validates actor capability, amount threshold, current version, and approval requirements in one transaction, then writes an approval decision and audit event. No real money movement occurs in MVP.

### `POST /api/v1/approvals/{id}/reject`

**Auth:** `resolution.approve.low` or `resolution.approve.high` according to the request policy.  
**Headers:** `Idempotency-Key` required.  
**Behavior:** records one policy-authorized rejection, transitions the simulated request to `REJECTED`, and leaves the source exception unchanged.

### `GET /api/v1/audit-events`

**Auth:** `audit.read`.  
**Query:** optional `resource_id`, maximum 128 characters.  
**Behavior:** returns organization-scoped control/investigation events. The demo adapter stores these in memory; production storage is append-only PostgreSQL.

The development actor context supports `ANALYST`, `FINANCE_MANAGER`, `CONTROLLER`, and `AUDITOR` roles through test-only headers. Only roles with `audit.read` receive this resource; organization scope is applied before serialization.

### `GET /api/v1/exceptions/{id}/graph`

**Auth:** `exception.read`.  
**Response:** `{ exception_id, organization_id, nodes, edges }`, where each node contains an entity type, display label, `CONFIRMED`/`MISSING` state, and optional integer minor-unit amount. Edges contain source, target, and a controlled relationship label.  
**Behavior:** derives a bounded lifecycle graph from canonical records for the requested organization. Missing inventory disposition or ERP reversal steps are represented as missing nodes when the lifecycle evidence does not confirm them. No graph database or hidden ground truth is consulted.  
**Failure:** `RESOURCE_NOT_FOUND` for unknown or cross-tenant exceptions.

### `GET /api/v1/patterns`

**Auth:** `analytics.read`.  
**Query:** `limit` from 1 through 50; default 20.  
**Response:** `PatternResponse[]`, sorted by occurrence count descending and then stable pattern ID. Each item includes exception type, occurrence count, associated exposure, location/workflow signature, observation, prevention recommendation, severity, and member order IDs.  
**Behavior:** deterministically reconciles the organization-scoped demo lifecycle set, groups repeatable exception signatures, and returns only groups with at least two occurrences. Recommendations are advisory signals, not causal findings or automatic controls.  
**Failure:** `FORBIDDEN` without `analytics.read`; the current demo implementation returns an empty collection when no group reaches the minimum occurrence threshold.

### `GET /api/v1/patterns/{id}`

**Auth:** `analytics.read`.  
**Behavior:** returns one organization-scoped pattern using the same deterministic grouping algorithm as the collection endpoint.  
**Failure:** `RESOURCE_NOT_FOUND` for an unknown pattern ID or a pattern not present in the caller's organization.

### `POST /api/v1/evaluation/run`

**Auth:** `analytics.read`.  
**Headers:** `Idempotency-Key` required.  
**Body:** `{ "orders": 1..10000, "seed": 0..2147483647, "anomaly_rate": 0..1 }`; defaults are 1000, 42, and 0.30.  
**Response:** evaluation ID, organization ID, run parameters, creation time, and the public metric report. The report includes lifecycle count, reconciliation counts, match rate, precision, exception recall, throughput, and unresolved exceptions. It never includes hidden labels or `ground_truth.json`.  
**Behavior:** runs the deterministic evaluator in process for the demo boundary and returns the same result when the same idempotency key and request are replayed. A reused key with a different request returns `IDEMPOTENCY_CONFLICT`.

### `GET /api/v1/evaluation/latest`

**Auth:** `analytics.read`.  
**Behavior:** returns the latest organization-scoped public evaluation report held by the demo service.  
**Failure:** `RESOURCE_NOT_FOUND` before an evaluation has run for that organization.

## Error codes

| Code | HTTP | Meaning |
| --- | --- | --- |
| `AUTHENTICATION_REQUIRED` | 401 | No valid session/token |
| `FORBIDDEN` | 403 | Actor lacks capability |
| `RESOURCE_NOT_FOUND` | 404 | Unknown or cross-tenant resource |
| `INVALID_REQUEST` | 422 | Schema or enum validation failed |
| `IDEMPOTENCY_CONFLICT` | 409 | Same key used with a different request |
| `INVALID_STATE` | 409 | Workflow transition is not allowed |
| `RATE_LIMITED` | 429 | Bounded action rate exceeded |
| `DEPENDENCY_UNAVAILABLE` | 503 | Safe dependency failure |

## API versioning and compatibility

## Storage selection and migrations

The API uses the deterministic in-process repository by default. Set `STORAGE_BACKEND=postgres` and a `DATABASE_URL` using the PostgreSQL repository path. Apply migrations explicitly with `fintrace-migrate`; application startup never mutates schema. Seed canonical demo records with `fintrace-seed` after migrations are applied. The current PostgreSQL path covers canonical reads, exception reads, aggregate reads, lifecycle reads, and audit event writes; investigation and control state persistence remains a later increment.

Breaking changes require `/api/v2` or an explicitly negotiated media type. Additive response fields are preferred. Clients must tolerate unknown response fields and must not infer authorization from omitted UI fields.
