import hashlib
from pathlib import Path

from app.persistence.connection import connection


class MigrationError(RuntimeError):
    pass


def migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(path for path in migrations_dir.glob("[0-9][0-9][0-9]_*.sql") if path.is_file())


def renamed_migration_version(applied: dict[str, str], name: str, checksum: str) -> str | None:
    """Adopt the exact, terminology-only revision of migration 012; never rerun it."""
    if name != "012_input_accounting_contract.sql":
        return None
    previous = [version for version in applied if version.startswith("012_") and version != name]
    if not previous:
        return None
    if (len(previous) != 1 or name in applied
        or applied[previous[0]] != "33f81dd434dd685544f6b87dc8c2bb1f3b7c53e48f2a09a859ec861620fad05b"
        or checksum != "2e67bcc6d398fe482be327d45dc42ff5950d9e8817d370358d9f628d53f5f8d7"):
        raise MigrationError("Unrecognized migration 012 revision; manual migration review required")
    return previous[0]


def apply_migrations(database_url: str, migrations_dir: Path) -> list[str]:
    files = migration_files(migrations_dir)
    if not files:
        raise MigrationError(f"No migration files found in {migrations_dir}")

    with connection(database_url) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("fintrace:schema",))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(128) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                checksum CHAR(64)
            )
            """
        )
        conn.execute("ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS checksum CHAR(64)")
        applied = {
            row["version"]: row["checksum"]
            for row in conn.execute("SELECT version, checksum FROM schema_migrations")
        }
        executed: list[str] = []
        for path in files:
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            previous = renamed_migration_version(applied, path.name, checksum)
            if previous:
                conn.execute("UPDATE schema_migrations SET version = %s, checksum = %s WHERE version = %s", (path.name, checksum, previous))
                continue
            if path.name in applied:
                if applied[path.name] and str(applied[path.name]) != checksum:
                    raise MigrationError(f"Migration checksum mismatch for {path.name}")
                if not applied[path.name]:
                    conn.execute(
                        "UPDATE schema_migrations SET checksum = %s WHERE version = %s",
                        (checksum, path.name),
                    )
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                (path.name, checksum),
            )
            executed.append(path.name)
        return executed
