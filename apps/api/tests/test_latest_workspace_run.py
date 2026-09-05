from app.repositories.sample import SampleRepository
from app.persistence.migrations import MigrationError, renamed_migration_version
import pytest


def test_latest_run_is_scoped_and_selected_by_time_not_close_creation():
    repo = SampleRepository()
    older = {"id": "run-old", "started_at": "2026-03-01T00:00:00Z"}
    latest = {"id": "run-new", "started_at": "2026-03-03T00:00:00Z", "status": "FAILED"}
    repo._reconciliation_runs = {
        ("org-a", "older-close"): [older, latest],
        ("org-a", "new-empty-close"): [],
        ("org-b", "other-close"): [{"id": "other", "started_at": "2026-04-01T00:00:00Z"}],
        ("org-a", "stale-close"): [{"id": "stale", "started_at": "2026-05-01T00:00:00Z", "is_stale": True}],
    }
    assert repo.latest_workspace_run("org-a") == latest
    assert repo.latest_workspace_run("org-missing") is None


def test_migration_rename_only_accepts_known_exact_revision():
    old = {"012_previous_contract.sql": "33f81dd434dd685544f6b87dc8c2bb1f3b7c53e48f2a09a859ec861620fad05b"}
    new = "2e67bcc6d398fe482be327d45dc42ff5950d9e8817d370358d9f628d53f5f8d7"
    assert renamed_migration_version(old, "012_input_accounting_contract.sql", new) == "012_previous_contract.sql"
    with pytest.raises(MigrationError):
        renamed_migration_version(old, "012_input_accounting_contract.sql", "tampered")
    with pytest.raises(MigrationError):
        renamed_migration_version({"012_previous_contract.sql": "unknown"}, "012_input_accounting_contract.sql", new)
    assert renamed_migration_version({}, "012_input_accounting_contract.sql", new) is None
