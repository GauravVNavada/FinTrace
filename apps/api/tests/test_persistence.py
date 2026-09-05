from pathlib import Path

from app.persistence.migrations import migration_files


def test_migrations_are_discovered_in_version_order() -> None:
    migrations = migration_files(Path(__file__).parents[1] / "migrations")

    assert [migration.name for migration in migrations] == [
        "001_initial_schema.sql",
        "002_controls_and_idempotency.sql",
        "003_exception_external_ids.sql",
        "004_workflow_persistence.sql",
        "005_financial_investigations_and_source_files.sql",
        "006_source_analysis_and_mappings.sql",
        "007_relationship_proposals.sql",
        "008_dataset_versions_and_lineage.sql",
        "009_investigation_reconciliation.sql",
        "010_financial_exception_investigations.sql",
            "011_uploaded_approval_requests.sql",
        "012_input_accounting_contract.sql",
        "013_provider_health_diagnostics.sql",
            "014_tenant_integrity_and_idempotency.sql",
            "015_source_content_deduplication.sql",
            "016_inventory_valuation.sql",
        ]
