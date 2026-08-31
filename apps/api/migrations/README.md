# FinTrace migrations

Migrations 001–011 define the seeded MVP canonical/workflow tables, source intake and analysis, relationship proposals, immutable normalized datasets, investigation-scoped reconciliation runs/results, uploaded-result exception investigations, and durable approval requests for uploaded results. Application startup must never apply migrations automatically.

Migrations are forward-only and version-controlled. Apply them only against an approved local/test PostgreSQL instance during the persistence sprint.

`001_initial_schema.sql` establishes the canonical MVP tables, organization-scoped uniqueness, integer minor-unit money fields, timezone-aware timestamps, foreign keys, check constraints, and access-path indexes. `002_controls_and_idempotency.sql` adds organization membership, idempotency responses, approval requests, and approval decisions for Sprint 4. `003_exception_external_ids.sql` adds stable public exception identifiers required by the API contract. `007_relationship_proposals.sql` stores deterministic join proposals and explicit review state. `008_dataset_versions_and_lineage.sql` stores immutable normalized snapshots and source lineage. `009_investigation_reconciliation.sql` stores deterministic run summaries and per-order results. `010_financial_exception_investigations.sql` stores bounded uploaded-exception investigation responses.

Do not run migrations from application startup. Run `fintrace-migrate` explicitly against the configured database. The runner records applied filenames and SHA-256 checksums in `schema_migrations`, takes a PostgreSQL advisory lock, and applies files in lexical order. Migrations 001–011 are applied and verified against the local Docker PostgreSQL instance on host port 55432.
