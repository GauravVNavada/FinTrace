import argparse
from pathlib import Path

from app.core.config import get_settings
from app.persistence.migrations import apply_migrations


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply FinTrace PostgreSQL migrations")
    settings = get_settings()
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path(settings.migrations_dir),
    )
    args = parser.parse_args()
    migrations_dir = args.migrations_dir
    if not migrations_dir.is_absolute():
        migrations_dir = Path(__file__).resolve().parents[2] / migrations_dir
    executed = apply_migrations(settings.database_url, migrations_dir)
    print(f"Applied {len(executed)} migration(s): {', '.join(executed) or 'none'}")
