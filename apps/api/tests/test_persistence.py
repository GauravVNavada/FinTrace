from pathlib import Path

from app.persistence.migrations import migration_files


def test_migrations_are_discovered_in_version_order() -> None:
    migrations = migration_files(Path(__file__).parents[1] / "migrations")

    assert [migration.name for migration in migrations] == [
        "001_initial_schema.sql",
        "002_controls_and_idempotency.sql",
        "003_exception_external_ids.sql",
        "004_workflow_persistence.sql",
    ]
