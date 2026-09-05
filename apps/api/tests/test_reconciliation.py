from datetime import UTC, datetime

import pytest

from app.domain.lifecycle import CanonicalLifecycle
from app.evaluation.metrics import evaluate_dataset
from app.reconciliation.engine import reconcile_dataset, reconcile_lifecycle
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
    assert first.exception_precision == second.exception_precision
    assert first.exception_recall == second.exception_recall
    assert first.severity_accuracy == second.severity_accuracy
    assert first.unsafe_resolution_rate is None
    assert first.resolution_decisions_evaluated == 0
    assert first.throughput_per_second > 0


def test_missing_uploaded_gateway_fee_is_a_controlled_result() -> None:
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-1", "amount_minor": 10000},
        payments=({"payment_id": "PAY-1", "amount_minor": 10000},),
        settlements=(
            {"settlement_id": "SET-1", "fees_minor": 0, "settled_at": "2026-08-03T00:00:00+00:00"},
        ),
        invoices=(),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )
    result = reconcile_lifecycle(lifecycle)
    assert result.status == "EXCEPTION"
    assert result.exception_type == "PAYMENT_FEE_MISSING"


def test_reconcile_lifecycle_accepts_timezone_aware_datetime_timestamps() -> None:
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-DATETIME", "amount_minor": 10000},
        payments=(
            {
                "payment_id": "PAY-DATETIME",
                "amount_minor": 10000,
                "gateway_fee_minor": 180,
                "captured_at": datetime(2026, 8, 1, tzinfo=UTC),
            },
        ),
        settlements=(
            {
                "settlement_id": "SET-DATETIME",
                "fees_minor": 180,
                "settled_at": datetime(2026, 8, 2, tzinfo=UTC),
            },
        ),
        invoices=({"invoice_id": "INV-DATETIME", "gross_minor": 10000, "status": "ACTIVE"},),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )

    result = reconcile_lifecycle(lifecycle)

    assert result.status == "RECONCILED"


def test_reconcile_lifecycle_accepts_a_reversed_invoice_for_a_refund() -> None:
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-REFUND", "amount_minor": 10000},
        payments=(
            {
                "payment_id": "PAY-REFUND",
                "amount_minor": 10000,
                "gateway_fee_minor": 180,
                "captured_at": "2026-01-01T08:00:00+00:00",
            },
        ),
        settlements=(
            {
                "settlement_id": "SET-REFUND",
                "fees_minor": 180,
                "settled_at": "2026-01-02T08:00:00+00:00",
            },
        ),
        invoices=(
            {"invoice_id": "INV-REFUND", "gross_minor": 10000, "status": "ACTIVE"},
            {"invoice_id": "INV-REVERSAL", "gross_minor": -10000, "status": "REVERSED"},
        ),
        refunds=({"refund_id": "REF-REFUND", "amount_minor": 10000},),
        inventory_movements=({"movement_type": "RETURN"},),
        employee_actions=(),
    )

    result = reconcile_lifecycle(lifecycle)

    assert result.status == "RECONCILED"


def test_timezone_naive_timestamps_are_rejected_before_subtraction():
    lifecycle = CanonicalLifecycle(
        order={"order_id": "ORD-NAIVE", "amount_minor": 10000},
        payments=(
            {
                "payment_id": "PAY-NAIVE",
                "amount_minor": 10000,
                "captured_at": "2026-08-01T00:00:00+00:00",
            },
        ),
        settlements=(
            {"settlement_id": "SET-NAIVE", "fees_minor": 0, "settled_at": "2026-08-02T00:00:00"},
        ),
        invoices=(),
        refunds=(),
        inventory_movements=(),
        employee_actions=(),
    )
    with pytest.raises(ValueError, match="timezone offset"):
        reconcile_lifecycle(lifecycle)


def _valued_inventory_lifecycle(refund=True, return_quantity=1, return_value=2400):
    return CanonicalLifecycle(
        order={"order_id": "ORD-INVENTORY", "amount_minor": 10000},
        payments=({"payment_id": "PAY-INVENTORY", "amount_minor": 10000, "gateway_fee_minor": 180},),
        settlements=({"settlement_id": "SET-INVENTORY", "fees_minor": 180, "tax_minor": 32, "net_minor": 9788},),
        invoices=({"invoice_id": "INV-INVENTORY", "gross_minor": 10000, "status": "ACTIVE"},),
        refunds=({"refund_id": "REF-INVENTORY", "amount_minor": 10000},) if refund else (),
        inventory_movements=(
            {"movement_id": "MOV-SALE", "movement_type": "SALE", "quantity": 1, "unit_cost_minor": 2400, "inventory_value_minor": 2400},
            {"movement_id": "MOV-RETURN", "movement_type": "RETURN", "quantity": return_quantity, "unit_cost_minor": 2400, "inventory_value_minor": return_value},
        ),
        employee_actions=(),
    )


def test_reconcile_detects_inventory_return_value_mismatch():
    result = reconcile_lifecycle(_valued_inventory_lifecycle(return_value=2550))
    assert result.status == "EXCEPTION"
    assert result.exception_type == "INVENTORY_VALUE_MISMATCH"
    assert any(finding.code == "INVENTORY_VALUE_MISMATCH" for finding in result.findings)


def test_reconcile_detects_inventory_return_quantity_mismatch():
    result = reconcile_lifecycle(_valued_inventory_lifecycle(return_quantity=2, return_value=4800))
    assert result.status == "EXCEPTION"
    assert result.exception_type == "INVENTORY_QUANTITY_MISMATCH"


def test_reconcile_detects_inventory_restored_without_refund():
    result = reconcile_lifecycle(_valued_inventory_lifecycle(refund=False))
    assert result.status == "EXCEPTION"
    assert result.exception_type == "INVENTORY_RESTORED_WITHOUT_REFUND"


def test_reconcile_detects_row_level_inventory_value_calculation_error():
    lifecycle = _valued_inventory_lifecycle(return_value=2400)
    lifecycle = lifecycle.__class__(
        order=lifecycle.order,
        payments=lifecycle.payments,
        settlements=lifecycle.settlements,
        invoices=lifecycle.invoices,
        refunds=(),
        inventory_movements=(
            {"movement_id": "MOV-SALE", "movement_type": "SALE", "quantity": 1, "unit_cost_minor": 2400, "inventory_value_minor": 2500},
        ),
        employee_actions=(),
    )
    result = reconcile_lifecycle(lifecycle)
    assert result.exception_type == "INVENTORY_VALUE_MISMATCH"
    assert any(finding.code == "INVENTORY_VALUE_CALCULATION_ERROR" for finding in result.findings)
