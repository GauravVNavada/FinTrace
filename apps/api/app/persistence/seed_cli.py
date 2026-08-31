import argparse

from app.core.config import get_settings
from app.persistence.seed import seed_database
from app.simulator.generator import GeneratorConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed FinTrace PostgreSQL with deterministic demo data"
    )
    parser.add_argument("--orders", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--anomaly-rate", type=float, default=0.30)
    parser.add_argument("--organization-id", default="ORG-001")
    args = parser.parse_args()
    result = seed_database(
        get_settings().database_url,
        GeneratorConfig(args.orders, args.seed, args.anomaly_rate, args.organization_id),
    )
    state = "already existed" if result.skipped else "seeded"
    print(
        f"{state}: {result.lifecycle_count} lifecycles, {result.exception_count} exceptions, run {result.run_key}"
    )
