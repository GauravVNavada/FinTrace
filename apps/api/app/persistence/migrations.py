from pathlib import Path

from app.persistence.connection import connection


class MigrationError(RuntimeError):
    pass


def migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(path for path in migrations_dir.glob("[0-9][0-9][0-9]_*.sql") if path.is_file())


def apply_migrations(database_url: str, migrations_dir: Path) -> list[str]:
    files = migration_files(migrations_dir)
    if not files:
        raise MigrationError(f"No migration files found in {migrations_dir}")

    with connection(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(128) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
        executed: list[str] = []
        for path in files:
            if path.name in applied:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            executed.append(path.name)
        return executed
