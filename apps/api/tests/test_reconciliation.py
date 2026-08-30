from app.evaluation.metrics import evaluate_dataset
from app.reconciliation.engine import reconcile_dataset
from app.simulator.generator import GeneratorConfig, generate_dataset


def test_reconciliation_maps_seeded_scenarios_to_safe_statuses() -> None:
    dataset = generate_dataset(GeneratorConfig(orders=500, seed=42, anomaly_rate=0.3))
    results = {result.order_id: result for result in reconcile_dataset(dataset)}

    expected = {
        "NORMAL": "RECONCILED",
        "SETTLEMENT_TIMING": "RECONCILED_WITH_VARIANCE",
        "SETTLEMENT_FEE_VARIANCE": "RECONCILED_WITH_VARIANCE",
        "MISSING_INVOICE": "EXCEPTION",
        "INVOICE_AMOUNT_MISMATCH": "EXCEPTION",
        "MISSING_SETTLEMENT": "EXCEPTION",
        "DUPLICATE_PAYMENT": "EXCEPTION",
        "REFUND_INVENTORY_MISSING": "EXCEPTION",
        "REFUND_ERP_REVERSAL_MISSING": "EXCEPTION",
        "PARTIAL_REFUND_MISMATCH": "EXCEPTION",
        "MANUAL_WORKFLOW_ANOMALY": "EXCEPTION",
        "AMBIGUOUS_PAYMENT": "AMBIGUOUS",
    }
    for truth in dataset.ground_truth:
        result = results[truth["order_id"]]
        assert result.status == expected[truth["exception_type"] or "NORMAL"]


def test_evaluation_is_reproducible_and_reports_throughput() -> None:
    config = GeneratorConfig(orders=500, seed=42, anomaly_rate=0.3)
    first, _ = evaluate_dataset(generate_dataset(config))
    second, _ = evaluate_dataset(generate_dataset(config))

    assert first.lifecycles == second.lifecycles == 500
    assert first.auto_reconciled == second.auto_reconciled
    assert first.exceptions == second.exceptions
    assert first.ambiguous == second.ambiguous
    assert first.match_rate == second.match_rate
    assert first.match_precision == second.match_precision
    assert first.exception_recall == second.exception_recall
    assert first.throughput_per_second > 0
