# FinTrace Schema

## Final intake and evidence corrections — 2026-09-05

See [final-validation.md](final-validation.md) for the current implementation and acceptance record. This correction supersedes older references to a hardwired August close, ID-prefix ambiguity, seed lifecycle detail, and automatic “Explained” labels for open exceptions.

Routine CSV/XLSX mapping is deterministic and source-scoped, with complete specialist field signatures preferred over filename words. Excel serial dates are converted only for recognized timestamp fields; captured/refunded monetary amounts are never dates. Unknown or incomplete input remains reviewable. A batch continues after an individual failure and refreshes uploaded sources; close execution waits for setup completion. Same-name changed content cannot silently replace a successful upload.

The read-only GET `/api/v1/financial-investigations/{id}/reconciliation-runs/{run_id}/results/{result_id}/lifecycle` returns the existing LifecycleResponse shape from the run’s normalized dataset, scoped to the authenticated tenant and latest run. No database migration. Missing evidence is displayed as missing, never substituted with exposure or seed data.

Deterministic controls check currency/status, payment amount, settlement gross/net arithmetic, and multiple settlement/refund review. Duplicate-payment conclusions require settlement coverage or distinct processor references, never an ID prefix. Open exceptions require a decision; ambiguous associations require evidence. Live AI remains read-only, provider-labeled and citation-verified; no change to financial authorization or automatic financial writes. The local demo is not a production banking integration.

## Investigation evidence improvement (2026-09-05)

No schema migration is required. Existing ToolCall provider/model fields identify mandatory collection as deterministic-evidence-collection / none. Response provider/model identify live synthesis. Legacy zero-lookup refreshes retain the persisted investigation ID so evidence-call foreign keys remain valid.

Status: accepted evolution schema; migrations 001–013 applied locally, migration 014 defined for tenant-integrity/replay hardening · 2026-09-03

## Domain separation for the evolution program

The existing exception-level investigation schema remains valid for `ExceptionInvestigation`. It must not be reused as the top-level workspace for uploaded source data.

| Entity | Purpose | Owns |
| --- | --- | --- |
| `FinancialInvestigation` | Top-level company/time-period analysis workspace | source files, mappings, relationships, dataset versions, runs, exceptions, patterns, and audit scope |
| `ExceptionInvestigation` | Investigation of one unresolved exception | bounded tool calls, structured result, evidence verification, and recommendation |
| `ReconciliationRun` | Deterministic execution over one dataset version | counts, statuses, exposure, throughput, and run lifecycle |
| `EvaluationRun` | Benchmark execution against hidden synthetic ground truth | measured deterministic/AI metrics and evaluation configuration |

Migration 005 adds the `financial_investigations` and `source_files` tables for the Sprint 1 source-intake boundary. Migration 006 adds tenant-scoped `source_analyses` and `source_mappings` for the Sprint 2 analysis/confirmation boundary. Migration 007 adds tenant-scoped `relationship_proposals`; proposals are deterministic evidence, never automatic acceptance. Migration 008 adds immutable `dataset_versions` and tenant-scoped `normalized_records` with source lineage. Migration 009 adds investigation-scoped `financial_reconciliation_runs` and `financial_reconciliation_results` linked to the immutable dataset version. Migration 010 adds uploaded-result `financial_exception_investigations` with durable bounded responses. Migration 011 allows `approval_requests` to reference either a canonical exception or an uploaded reconciliation result, enforcing exactly one subject. Migration 015 adds `source_files.content_sha256` and its investigation-scoped lookup index for repeat-upload deduplication. Existing canonical entities and migration ordering must be preserved.

Fresh synthetic source generation does not add a parallel schema: it persists generated CSV exports through `source_files`, then follows the same analysis, mapping, relationship, normalization, reconciliation, and uploaded-result investigation boundaries. The seeded `exceptions` table remains a compatibility resource and is not a hidden projection of `financial_reconciliation_results`.

## Canonical lifecycle

```text
OrderLifecycle
├── order
├── payment[]
├── settlement[]
├── invoice[]
├── refund[]
├── inventory_movements[]
└── employee_actions[]
```

Every business-scoped record includes `organization_id`. IDs are immutable external references; internal database IDs are separate and never used as a substitute for source references.

## Core entities

| Entity | Required fields | Relationships |
| --- | --- | --- |
| Order | id, organization_id, store, total, status, created_at | has payments, invoice, refunds, inventory |
| Payment | id, organization_id, order_id, amount, status, fee, captured_at | has settlements and refunds |
| Settlement | id, organization_id, payment_id, gross, fees, tax, net, settled_at | references payment |
| Invoice | id, organization_id, order_id, gross, tax, status, created_at | references order |
| Refund | id, organization_id, payment_id, amount, status, processed_at | references payment |
| Inventory movement | id, organization_id, order_id, sku, quantity, type, occurred_at | references order |
| Employee action | id, organization_id, entity_type, entity_id, employee_id, action, occurred_at | references any lifecycle entity |
| Exception | id, organization_id, order_id, type, severity, status, exposure, detected_at | has evidence, investigation, recommendation |
| Audit event | id, organization_id, actor, action, resource, correlation_id, created_at | append-only |
| Organization member | id, organization_id, actor_id, role, created_at | one role per organization actor |
| Idempotency key | id, organization_id, actor_id, request_hash, response, expires_at | one response per organization/key |
| Approval request | id, organization_id, exception_id, action, status, threshold, requester, created_at | has approval decisions |
| Approval decision | id, organization_id, approval_request_id, actor_id, decision, created_at | one decision per actor/request |
| Investigation | id, organization_id, source_investigation_id, exception_id, status, response, created_at | one durable structured result per public investigation ID |
| Investigation tool call | id, organization_id, investigation_id, sequence_no, name, payload, created_at | ordered, organization-scoped read-only evidence calls |
| Evaluation run | id, organization_id, source_evaluation_id, response, created_at | latest public benchmark result per organization |
| Financial investigation | id, organization_id, source_investigation_id, name, period, base_currency, status, created_by, created_at | owns source files and later immutable dataset versions |
| Source file | id, organization_id, financial_investigation_id, source_file_id, original_filename, storage_reference, mime_type, size_bytes, row/column counts, content_sha256, status, created_at | metadata, content identity, and generated storage reference for one bounded upload; non-ready rows can be replaced by a same-name upload |

## Reconciliation status

`RECONCILED`, `RECONCILED_WITH_VARIANCE`, `EXCEPTION`, `AMBIGUOUS`, and `PENDING` are mutually exclusive. A status must be derived by deterministic rules; a model cannot write it.

## Exception schema

The public exception identifier is `source_exception_id` and is unique within an organization. The PostgreSQL primary key remains an internal UUID; API clients must never depend on it.

```json
{
  "id": "EXC-1042",
  "organization_id": "ORG-001",
  "order_id": "ORD-2041",
  "type": "REFUND_WITHOUT_INVENTORY_RETURN",
  "severity": "HIGH",
  "status": "OPEN",
  "financial_exposure": 18740,
  "currency": "INR",
  "detected_at": "2026-08-30T12:00:00+05:30",
  "rules_triggered": ["REFUND_EXISTS", "INVENTORY_RETURN_MISSING"]
}
```

## Investigation result

Investigation output is strict and uses controlled codes. The evidence score is calculated by the verifier, not supplied by the model. `UNRESOLVED` is a valid result and must not be coerced into a root cause.

```json
{
  "status": "SUPPORTED",
  "root_cause_code": "INCOMPLETE_REFUND_WORKFLOW",
  "summary": "Refund completed but downstream operational reversal did not complete.",
  "supporting_evidence": [{ "source": "refund", "record_id": "RFND-2991", "fact": "Full refund completed" }],
  "contradictory_evidence": [],
  "missing_evidence": ["Physical goods receipt confirmation"],
  "recommended_action_code": "REQUEST_INVENTORY_VERIFICATION",
  "requires_human_review": true
}
```

## Controlled taxonomies

Root cause codes include `SETTLEMENT_TIMING`, `SETTLEMENT_FEE_VARIANCE`, `SETTLEMENT_MISSING`, `DUPLICATE_PAYMENT`, `ERP_INVOICE_MISSING`, `ERP_AMOUNT_MISMATCH`, `INCOMPLETE_REFUND_WORKFLOW`, `INVENTORY_REVERSAL_MISSING`, `ERP_REVERSAL_MISSING`, `REFERENCE_MAPPING_FAILURE`, `PARTIAL_REFUND_MISMATCH`, `DATA_QUALITY_ERROR`, `INVENTORY_VALUE_MISMATCH`, `INVENTORY_QUANTITY_MISMATCH`, `INVENTORY_RESTORED_WITHOUT_REFUND`, `INVENTORY_VALUE_CALCULATION_ERROR`, `AMBIGUOUS_ASSOCIATION`, and `UNKNOWN`.

## Workflow persistence

Migration `004_workflow_persistence.sql` adds durable JSONB response snapshots for investigations and evaluations, ordered tool-call records, public identifiers for approval requests/decisions, and organization-scoped foreign keys. Consequential response replay is backed by `idempotency_keys`; the stored request hash must match before a previous response is returned. The JSONB snapshot is a projection of validated API models, not an authority for monetary arithmetic or authorization.

## Change policy

Adding or removing a field, enum, relationship, or status requires updating this document, the API contract, tests, and the PRD section that defines the behavior.

## Relational design details

### Money and time

Money is stored as `NUMERIC(18,2)` in persistence or integer minor units where a source supports minor units. Application calculations use decimal-safe types. Currency is explicit on monetary aggregates, and mixed-currency lifecycles are rejected for MVP. All event timestamps are `TIMESTAMPTZ` and are normalized to UTC at ingestion; display conversion happens at the edge.

### Keys and constraints

- Internal primary keys are UUIDs.
- Source IDs are immutable and unique within `(organization_id, source_system, source_id)`.
- Every child record has a foreign key to its canonical parent where the source relationship is known.
- Status values use checked enums rather than arbitrary strings.
- `financial_exposure >= 0`.
- `settlement.net = settlement.gross - settlement.fees - settlement.tax - refund_adjustments` is validated by the reconciliation service and stored for explainability.
- An exception has one current status but retains all state changes in audit history.

### Suggested table inventory

```text
organizations
users
roles / permissions / role_permissions
orders / order_items
payments / settlements / refunds
invoices / inventory_movements / employee_actions
reconciliation_runs / reconciliation_results
exceptions / exception_evidence
investigations / investigation_tool_calls / investigation_results
recommendations / approval_requests / approval_decisions
audit_events
exception_patterns / pattern_members
```

### Indexing baseline

Every business table gets an organization index. High-volume access paths use composite indexes beginning with `organization_id`, followed by the filter and sort columns, for example `(organization_id, status, detected_at DESC)` on exceptions and `(organization_id, order_id)` on source entities. All list endpoints are paginated; no production endpoint may return an unbounded table.

### Delete and retention behavior

Source financial records and audit events are append-only for MVP. Corrections arrive as new source events or explicit adjustment records. Soft deletion is not used to hide financial history. Production retention, legal hold, archival, and PII deletion rules must be approved before live data is introduced.

## Migration rules

Migrations are version-controlled and forward-compatible. Required changes follow expand → backfill → validate → contract. Do not add a required column to a populated table without a safe default/backfill plan. Large indexes use the database's online/concurrent facility where supported. Destructive operations require a backup, migration review, and recovery test.

## Migration 014 integrity additions (2026-09-03)

`014_tenant_integrity_and_idempotency.sql` adds organization-aware composite foreign keys for payments, settlements, invoices, refunds, and inventory movements, plus supporting indexes for bounded audit and reconciliation-result reads. Repository lookups also join on organization ID, so an internal identifier cannot resolve through another tenant's parent row. Pending PostgreSQL idempotency records carry a finite lease and can be safely reclaimed after expiry; completed responses remain replayable by request hash.

## Tenant isolation review

The repository contract must make `organization_id` a required argument, not an optional filter. Tests must include two organizations with identical source IDs and assert that reads, writes, investigation tools, aggregates, and audit history cannot cross the boundary.

Sprint 3 uses canonical lifecycle records and bounded investigation tools. Sprint 4 defines `organization_members`, `idempotency_keys`, `approval_requests`, and `approval_decisions` in migration 002; migration 003 adds stable public exception IDs; migration 004 adds durable investigations, ordered tool calls, evaluations, and public workflow identifiers; migration 005 adds financial-investigation/source-file intake; migration 006 adds source analyses and mappings. The PostgreSQL repository supports canonical lifecycle, exception, aggregate, audit, financial investigation, source analysis, mapping, investigation, evaluation, and control reads/writes when `STORAGE_BACKEND=postgres`. The demo runtime keeps an equivalent process-local contract for isolated tests.

## Inventory valuation additions

`inventory_movements` includes optional `unit_cost_minor` and `inventory_value_minor` columns from migration 016. The values are nullable for ordinary source exports and non-negative when present. The reconciliation engine derives expected cost value as `unit_cost_minor * quantity` and never treats customer refund amount as inventory cost. Inventory mismatch findings include missing returns, quantity differences, return-value differences, and row-level value-calculation errors.
