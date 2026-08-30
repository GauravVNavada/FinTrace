# FinTrace migrations

Migrations are forward-only and version-controlled. Apply them only against an approved local/test PostgreSQL instance during the persistence sprint.

`001_initial_schema.sql` establishes the canonical MVP tables, organization-scoped uniqueness, integer minor-unit money fields, timezone-aware timestamps, foreign keys, check constraints, and access-path indexes. `002_controls_and_idempotency.sql` adds organization membership, idempotency responses, approval requests, and approval decisions for Sprint 4.

Do not run migrations from application startup. A later persistence increment should add a migration runner and a schema compatibility check in CI. These migrations have not been applied on this workstation because PostgreSQL is not installed.
