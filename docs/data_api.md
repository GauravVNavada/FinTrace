# FinTrace Data and API Contract

Status: accepted evolution contract; Sprints 1–7 plus Track 4 reliability/UX hardening implemented · 2026-09-03

## Adapter rule

The web application uses typed API clients for dashboard summary, exception queue/detail, investigations, patterns, evaluations, audit activity, and the financial-investigation workflow. Financial-investigation run metrics, results, advisory patterns, uploaded exception investigation traces, source generation, lifecycle detail, and audit events are API-backed. The seeded exception queue remains a separate compatibility resource; uploaded results are not silently merged into it. Components consume domain objects from client mapping functions and may not duplicate financial records or implement reconciliation logic.

## Active API evolution

The upload workflow introduces a separate `FinancialInvestigation` resource. It is distinct from the existing exception-level `ExceptionInvestigation` routes. Sprint 1 implements the minimum coherent contracts:

```text
POST /api/v1/financial-investigations
GET  /api/v1/financial-investigations
POST /api/v1/financial-investigations/flagship-demo
GET  /api/v1/financial-investigations/{id}
POST /api/v1/financial-investigations/{id}/sources
GET  /api/v1/financial-investigations/{id}/sources
DELETE /api/v1/financial-investigations/{id}/sources/{source_id}
POST /api/v1/financial-investigations/{id}/demo-data
```

The upload endpoints validate organization scope, multipart metadata, extension/content consistency, compressed and uncompressed size/archive-member budgets, extracted row/column limits, safe generated storage names, and idempotency. An already successful source is a locked logical source: re-uploading its bytes, even with a new filename or idempotency key, is a no-op and the response marks it with `deduplicated: true`. A source still in `MAPPING_REQUIRED`, `FAILED`, or another non-ready state is replaceable by a later upload with the same filename; the unresolved copy and its derived metadata are removed before the replacement is attached. Structural source analysis is explicitly sample-bounded; normalization parses through the configured row limit and rejects overflow rather than silently truncating. Sprint 2 adds bounded source analysis and explicit mapping review. Sprint 3 adds deterministic relationship proposals and immutable dataset-version normalization with source lineage; lifecycle and reconciliation endpoints must remain scoped to the financial investigation and its immutable dataset version.

### Fresh synthetic source generation

`POST /financial-investigations/{id}/demo-data` requires `Idempotency-Key` and accepts bounded `orders`, `seed`, `anomaly_rate`, and optional allowlisted `scenario_types`. It is available only for a workspace with no attached sources, creates separate orders/payments/settlements/invoices/refunds/inventory/employee-action CSV exports, and stores them through the same upload and audit pipeline as user-provided files. Generation never exposes hidden labels, never bypasses analysis/mapping/relationship confirmation, and cannot overwrite an existing source set. Reusing the same idempotency key and request replays the generated source response; a different request conflicts.

`POST /financial-investigations/flagship-demo` creates or resumes the local prepared investigation, runs the existing synthetic upload, source analysis, mapping confirmation, relationship review, immutable normalization, and deterministic reconciliation stages, then returns the persisted investigation. It is a local demo convenience endpoint; it does not hardcode metrics or AI conclusions and requires the same write capability and idempotency header as the underlying stages.

### Sprint 1 implemented source contract

`POST /financial-investigations` requires `Idempotency-Key` and a name, period start/end, and three-letter base currency. The API creates a `DRAFT` investigation in the caller's organization. `POST /financial-investigations/{id}/sources` requires a multipart `file` field and `Idempotency-Key`; only UTF-8 CSV and OOXML XLSX are accepted. The API returns bounded metadata including original display filename, byte size, row count, column count, status, creation time, and whether the upload was deduplicated. Raw file bytes are stored under a generated server reference and are not included in API responses. Source replacement and deduplication are scoped to the investigation; the same bytes may be attached to a different investigation.

`GET` list/detail/source routes are organization-scoped. Reusing an upload idempotency key replays the original response; reusing it with a different request is a conflict. Deleting a source removes its generated stored file and writes `SOURCE_FILE_DELETED` to the audit stream. Source status is `UPLOADED` until analysis begins, `MAPPING_REQUIRED` after proposals are persisted, and `READY` only after required mappings are explicitly confirmed.

### Sprint 2 implemented source-analysis contract

```text
POST  /financial-investigations/{id}/sources/{source_id}/analyze
GET   /financial-investigations/{id}/sources/{source_id}/analysis
GET   /financial-investigations/{id}/sources/{source_id}/mappings
PATCH /financial-investigations/{id}/sources/{source_id}/mappings/{mapping_id}
POST  /financial-investigations/{id}/sources/{source_id}/mappings/confirm
PATCH /financial-investigations/{id}/sources/{source_id}/classification
POST  /financial-investigations/{id}/relationships/discover
GET   /financial-investigations/{id}/relationships
PATCH /financial-investigations/{id}/relationships/{relationship_id}
```

Analysis is bounded to structural metadata and limited samples read from the generated server reference. The default provider is explicitly `OFFLINE_DETERMINISTIC`; an OpenAI-compatible provider is used only when configured. Provider output is validated against allowlisted source types and canonical fields. The deterministic mapper recognizes both human-readable money headers (for example, `gateway_fee`) and canonical minor-unit export headers (for example, `gateway_fee_minor`) without changing their required explicit confirmation. Confirmation is blocked when required mappings are absent or ignored, and no normalization or reconciliation is implied by a successful analysis.

Relationship discovery uses only confirmed mappings and deterministic overlap of supported join fields. It returns `PROPOSED` relationships with evidence and confidence; only an explicit authorized decision can move one to `ACCEPTED`, `REJECTED`, or `EDITED`.

### Sprint 3–7 dataset, investigation, signal, and demo contract

```text
POST /financial-investigations/{id}/dataset-versions/normalize
GET  /financial-investigations/{id}/dataset-versions/latest
GET  /financial-investigations/{id}/dataset-versions/{dataset_version_id}/records
POST /financial-investigations/{id}/reconciliation-runs
GET  /financial-investigations/{id}/reconciliation-runs/latest
GET  /financial-investigations/{id}/reconciliation-runs/{run_id}/results
POST /financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/investigate
GET  /financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/investigation
GET  /financial-investigations/{id}/patterns
POST /financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/resolution-request
```

Normalization is blocked until every source has confirmed required mappings and every discovered relationship has an explicit decision. Unknown source classifications, rows with extra cells, timezone-naive timestamps, unsupported duplicate invoices, and normalized rows without a canonical relationship key are refused instead of ignored. The bounded XLSX reader converts date-like Excel serial cells and naive spreadsheet datetimes into UTC timestamps before this validation; ordinary numeric cells remain unchanged. A single active invoice plus explicit `REVERSED` invoice rows is retained as one refund lifecycle and all rows remain accounted for; refund workflow actions whose `entity_type` is `REFUND` are linked through `refund_id`; multiple active invoices or other ambiguous invoice duplicates remain blocked. Monetary source fields are converted from decimal major units to integer minor units using decimal-safe rounding; malformed dates, monetary values, duplicate source IDs, duplicate orders, and ambiguous lifecycle construction remain explicit failures. Each source type has one canonical primary source-record ID for duplicate detection and lineage: `order_id` for `ORDERS`, `payment_id` for `PAYMENTS`, `settlement_id` for `SETTLEMENTS`, `refund_id` for `REFUNDS`, `invoice_id` for `INVOICES`, `movement_id` for `INVENTORY_MOVEMENTS`, and `action_id` for `EMPLOYEE_ACTIONS`. Other mapped IDs remain available for joins, so multiple payments may share an `order_id` while their `payment_id` values remain unique. Reconciliation requires `Idempotency-Key`, reads every row in the selected immutable dataset version for lifecycle construction, constructs lifecycles deterministically, persists one result per order, and records exception-created and run-completed audit events; the public normalized-records endpoint remains separately bounded for interactive reads. The uploaded-exception investigation endpoint also requires `Idempotency-Key`; it reconstructs only the selected result's scoped lifecycle, lets the configured provider select from an allowlisted read-only tool set, validates the bounded plan and provider output against cited records and deterministic exception compatibility, and persists `SUPPORTED`, `UNRESOLVED`, or `FAILED`. Relationship ambiguity is `UNRESOLVED`; provider outage is `FAILED` with an explicit unavailable status. Its result can be retrieved through the scoped run/result investigation route, including the validated evidence score and read-only tool trace. It cannot alter normalized data, reconciliation results, or external financial state. Investigation patterns group repeated exception types from the latest run and are advisory signals only; they do not prove a common root cause. Uploaded datasets are not evaluated against hidden ground truth until a labeled evaluation contract is introduced.

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

### `POST /api/v1/auth/demo-login`

**Auth:** none in `AUTH_MODE=development`; disabled in required-auth deployments.
**Request:** `{ "role": "ANALYST" | "FINANCE_MANAGER" | "CONTROLLER" }`
**Behavior:** returns a short-lived signed development identity containing the demo organization, actor, and role. The browser stores the token and sends it through the normal bearer-auth path; this endpoint does not change identity from a URL or route.

### `GET /ready`

**Auth:** none for local process checks.  
**Behavior:** returns `ready` for the demo backend; when `STORAGE_BACKEND=postgres`, performs a bounded database connectivity check and returns `503` if the database is unavailable. This endpoint does not run migrations.

```text
GET  /api/v1/dashboard/summary
GET  /api/v1/exceptions
GET  /api/v1/exceptions/{id}
GET  /api/v1/exceptions/{id}/graph
GET  /api/v1/lifecycles/{order_id}

POST /api/v1/exceptions/{id}/investigations
GET  /api/v1/investigations/{id}
GET  /api/v1/investigations/{id}/tool-calls

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
- Consequential POST requests and all source workflow mutations require `Idempotency-Key`: source delete, analysis, mapping edit/confirmation, and classification update are replay-safe and reject request-hash reuse. Pending work uses a finite lease in PostgreSQL.
- All query filters are validated against allowlisted enum values.
- Collection endpoints accept bounded `limit` values and every response carries and logs a `request_id`; audit events use it as the default correlation ID. Audit reads default to 200 and cap at 500.

## Investigation contract

The server sends exception metadata and tool definitions to the provider. It does not send every table. Each tool returns structured JSON and is scoped to the authenticated organization. The server validates the model result, verifies evidence existence and support, computes the evidence score, and persists the validated result plus ordered tool calls in PostgreSQL mode. `AI_PROVIDER`/`AI_MODEL` select the primary at runtime; `AI_FALLBACK_PROVIDER`, `GROQ_MODEL`, and provider-specific credentials select an explicit fallback. Key pools retry in order only for bounded transient failures; quota, authorization, unsupported-capability, and malformed-output failures are not hidden. Investigation persistence includes `originally_requested_provider`, `actual_provider_used`, `model_used`, `fallback_used`, and `fallback_reason`. The deterministic provider is the default local implementation for tests/offline operation only.

`GET /api/v1/ai/provider-health` requires the authenticated `financial_investigation.read` capability and returns compatibility fields for the active provider plus `overall_status`, `active_provider`, and a `providers` array containing separate configured model, reachability, latency, and redacted error-category entries for primary and fallback. Health uses one minimal structured/tool-capability probe per provider and caches results briefly so UI reads do not poll generation endpoints.

Relationship discovery and relationship decisions require `Idempotency-Key`. Reusing a key with the same operation replays the original proposal/decision; a different operation conflicts. Accepted or rejected proposals are audited, and normalization remains blocked until every proposal has an explicit decision.

## Caching and freshness

Dashboard aggregates may be cached by reconciliation run ID. Exception detail and audit history should be read fresh. No source record should be cached across organization scopes.

## Data migration rule

When persistence is introduced, create an explicit migration for each schema change. Do not mutate tables at application startup. Update [`docs/schema.md`](schema.md) and the PRD in the same pull request.

## Endpoint specifications

### `GET /api/v1/dashboard/summary`

**Auth:** `dashboard.read`  
**Query:** `run_id` optional; defaults to the latest completed run.  
**Response:** lifecycle count, auto-reconciled count, exception count, exposure, review count, run metadata.  
**Failure:** `RUN_NOT_FOUND`, `AGGREGATE_UNAVAILABLE`.

### `GET /api/v1/exceptions`

**Auth:** `exception.read`  
**Query:** `status`, `severity`, `type`, `assignee`, `cursor`, `limit` (maximum 100), and `q` (maximum 100 characters).  
**Ordering:** severity rank, then `detected_at DESC`.  
**Response (current MVP):** `ExceptionSummary[]`. The implementation returns the bounded seeded queue directly; cursor pagination is the next compatibility-preserving API extension before production-scale queues.
**Failure:** `INVALID_FILTER`, `TENANT_CONTEXT_REQUIRED`.

### `GET /api/v1/exceptions/{id}`

**Auth:** `exception.read`  
**Response:** exception metadata, exposure, and deterministic rule findings. Missing ERP invoice findings use the completed order amount as potential exposure rather than zero. The web detail view then retrieves the canonical lifecycle, derived graph, and resource-scoped audit events through their separate APIs; it does not use a client-side detail fixture.
**Authorization:** object-level organization ownership is checked before lookup result is returned. A cross-tenant ID returns the same not-found shape as an unknown ID.

### `GET /api/v1/lifecycles/{order_id}`

**Auth:** `exception.read`  
**Response:** canonical order, payments, settlements, invoices, refunds, inventory movements, and employee actions for one order.  
**Authorization:** the authenticated organization is applied to every related read; unknown and cross-tenant lifecycles return the same `RESOURCE_NOT_FOUND` shape.  
**Current implementation:** the development adapter reads the deterministic seed-42 dataset; PostgreSQL mode reads the organization-scoped seeded tables and applies the same contract.

### `POST /api/v1/exceptions/{id}/investigations`

**Auth:** `exception.investigate`  
**Headers:** `Idempotency-Key` required.  
**Behavior:** collects bounded read-only evidence and returns a structured investigation result. It does not approve or resolve.  
**Failure:** `EXCEPTION_NOT_FOUND`, `INVESTIGATION_IN_PROGRESS`, `PROVIDER_UNAVAILABLE` (503 with a safe failed result), `RESULT_REJECTED` (unresolved result requiring review).

**Current compatibility demo:** `EXC-1042` in `ORG-001` is a seeded exception resource. Its lifecycle and evidence are read through the same organization-scoped APIs as the rest of the legacy compatibility surface; the detail UI does not substitute a hardcoded snapshot when the resource is absent.

### `POST /api/v1/exceptions/{id}/resolution-request`

**Auth:** `resolution.request`
**Headers:** `Idempotency-Key` required.
**Behavior:** creates one approval request if policy requires it; otherwise returns a simulated safe action only where explicitly allowlisted.  
**Failure:** `ACTION_NOT_ALLOWED`, `APPROVAL_REQUIRED`, `INVALID_STATE`, `IDEMPOTENCY_CONFLICT`.

**Current implementation:** resolution and approval state is persisted through the repository contract in PostgreSQL mode. Bearer tokens signed with the configured HS256 secret carry `sub`, `organization_id`, `role`, `iss`, `aud`, `iat`, and `exp`. `X-Actor-*` headers are accepted only in development mode.

### `POST /api/v1/financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/resolution-request`

**Auth:** `resolution.request`
**Headers:** `Idempotency-Key` required.
**Behavior:** converts the selected uploaded `EXCEPTION` or `AMBIGUOUS` result into the same server-side approval policy used by the legacy exception queue. It records `REVIEW_REQUESTED` and does not mutate financial state. Duplicate keys replay the original request; different payloads conflict.

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
**Behavior:** returns organization-scoped control/investigation events. The demo adapter stores these in process for isolated tests; PostgreSQL storage is append-only and durable.

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
**Response:** evaluation ID, organization ID, run parameters, creation time, and the public metric report. The report includes lifecycle count, reconciliation counts, match rate, match precision, exception precision (status and type), exception recall, severity accuracy, throughput, unresolved exceptions, and an explicit unsafe-resolution metric state. Unsafe resolution is `null` with zero decisions when the benchmark contains no approval decisions; it is not presented as a measured zero. It never includes hidden labels or `ground_truth.json`.
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

The buildathon/demo runtime uses PostgreSQL: set `STORAGE_BACKEND=postgres` and a `DATABASE_URL` using the PostgreSQL repository path. Apply migrations explicitly with `fintrace-migrate`; application startup never mutates schema. Seed canonical demo records with `fintrace-seed` after migrations are applied. PostgreSQL mode covers canonical reads, exception reads, aggregate reads, lifecycle reads, investigation/evaluation/control persistence, idempotency replay, and audit writes. The deterministic in-process repository remains available for tests and offline fixtures. Set `AUTH_MODE=required` for deployment so tenant and actor scope must come from a verified bearer token.

Breaking changes require `/api/v2` or an explicitly negotiated media type. Additive response fields are preferred. Clients must tolerate unknown response fields and must not infer authorization from omitted UI fields.
# P0 additions

Migration 012 adds reconciliation input accounting (`records_expected`, `records_loaded`, `records_consumed`, orphan/rejected counts, and explicit incomplete/stale reasons), result/finding exposure categories, source-analysis provider/model metadata, relationship evidence metrics, and first-class uploaded-investigation metadata/tool-call rows. The current reconciliation response is valid only when all intended normalized records are consumed. AI source analysis and investigation provider status are returned explicitly; offline deterministic output is never labelled as live AI.

Inventory normalized records may additionally expose `unit_cost_minor` and `inventory_value_minor`. These are optional source-derived fields. Uploaded reconciliation results may use `INVENTORY_VALUE_MISMATCH`, `INVENTORY_QUANTITY_MISMATCH`, and `INVENTORY_RESTORED_WITHOUT_REFUND` exception types. The investigation response remains structured, tenant-scoped, cited, verifier-checked, and provider-labelled.
