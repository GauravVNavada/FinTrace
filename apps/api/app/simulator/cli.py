import argparse
from pathlib import Path

from app.simulator.generator import GeneratorConfig, generate_dataset, write_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a reproducible FinTrace synthetic batch")
    parser.add_argument("--orders", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--anomaly-rate", type=float, default=0.30)
    parser.add_argument("--output", type=Path, default=Path("data/generated"))
    args = parser.parse_args()
    dataset = generate_dataset(
        GeneratorConfig(orders=args.orders, seed=args.seed, anomaly_rate=args.anomaly_rate)
    )
    output = write_dataset(dataset, args.output)
    print(f"Generated {args.orders} lifecycles with seed {args.seed} at {output}")
