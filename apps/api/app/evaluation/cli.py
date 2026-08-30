import argparse

from app.evaluation.metrics import evaluate_dataset
from app.simulator.generator import GeneratorConfig, generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic FinTrace reconciliation")
    parser.add_argument("--orders", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--anomaly-rate", type=float, default=0.30)
    args = parser.parse_args()
    report, _ = evaluate_dataset(generate_dataset(GeneratorConfig(args.orders, args.seed, args.anomaly_rate)))
    print("=== FINTRACE BENCHMARK ===")
    print(f"Lifecycles: {report.lifecycles}")
    print(f"Auto reconciled: {report.auto_reconciled}")
    print(f"Exceptions: {report.exceptions}")
    print(f"Ambiguous: {report.ambiguous}")
    print(f"Match rate: {report.match_rate}%")
    print(f"Match precision: {report.match_precision}%")
    print(f"Exception recall: {report.exception_recall}%")
    print(f"Records / second: {report.throughput_per_second}")
    print(f"Unresolved exceptions: {report.unresolved_exceptions}")
