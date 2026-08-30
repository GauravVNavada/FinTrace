# FinTrace migrations

Migrations are forward-only and version-controlled. Apply them only against an approved local/test PostgreSQL instance during the persistence sprint.

`001_initial_schema.sql` establishes the canonical MVP tables, organization-scoped uniqueness, integer minor-unit money fields, timezone-aware timestamps, foreign keys, check constraints, and access-path indexes. `002_controls_and_idempotency.sql` adds organization membership, idempotency responses, approval requests, and approval decisions for Sprint 4. `003_exception_external_ids.sql` adds stable public exception identifiers required by the API contract.

Do not run migrations from application startup. Run `fintrace-migrate` explicitly against the configured database. The runner records applied filenames in `schema_migrations` and applies files in lexical order. Migrations 001–004 have been applied and verified against the local Docker PostgreSQL instance on host port 55432.
