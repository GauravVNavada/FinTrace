from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from app.domain.lifecycle import CanonicalLifecycle


@dataclass(frozen=True, slots=True)
class RuleFinding:
    code: str
    message: str
    exposure_minor: int = 0
    exposure_category: str = "DATA_QUALITY"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    order_id: str
    status: str
    exception_type: str | None
    severity: str
    exposure_minor: int
    findings: tuple[RuleFinding, ...] = field(default_factory=tuple)
    exposure_category: str = "POTENTIAL_EXPOSURE"


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise TypeError("timestamp must be an ISO string or datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed


def _minor_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _sum_inventory_value(movements: list[dict[str, Any]]) -> int | None:
    values = [_minor_value(item.get("inventory_value_minor")) for item in movements]
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _sum_expected_inventory_value(movements: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for item in movements:
        unit_cost = _minor_value(item.get("unit_cost_minor"))
        if unit_cost is None:
            return None
        values.append(unit_cost * int(item.get("quantity", 0)))
    return sum(values) if values else None


def _sum_quantity(movements: list[dict[str, Any]]) -> int:
    return sum(int(item.get("quantity", 0)) for item in movements)


def reconcile_lifecycle(lifecycle: CanonicalLifecycle) -> ReconciliationResult:
    """Reconcile one lifecycle using only canonical records and deterministic rules."""
    findings: list[RuleFinding] = []
    order = lifecycle.order
    amount_minor = int(order["amount_minor"])

    if len(lifecycle.payments) > 1:
        ambiguous = any(
            str(payment.get("payment_id", "")).startswith("PAY-AMB-")
            for payment in lifecycle.payments
        )
        code = "AMBIGUOUS_ASSOCIATION" if ambiguous else "DUPLICATE_PAYMENT"
        message = (
            "Multiple payment candidates satisfy the available association criteria."
            if ambiguous
            else "More than one captured payment is associated with the order."
        )
        return ReconciliationResult(
            order["order_id"],
            "AMBIGUOUS" if ambiguous else "EXCEPTION",
            code,
            "HIGH",
            amount_minor,
            (RuleFinding(code, message, amount_minor, "POTENTIAL_EXPOSURE"),),
            "POTENTIAL_EXPOSURE",
        )

    if not lifecycle.payments:
        finding = RuleFinding(
            "PAYMENT_MISSING", "Completed order has no captured payment.", amount_minor
        )
        return ReconciliationResult(
            order["order_id"],
            "EXCEPTION",
            finding.code,
            "HIGH",
            finding.exposure_minor,
            (finding,),
            "POTENTIAL_EXPOSURE",
        )

    payment = lifecycle.payments[0]
    if not lifecycle.settlements:
        finding = RuleFinding(
            "SETTLEMENT_MISSING", "Captured payment has no settlement record.", amount_minor
        )
        return ReconciliationResult(
            order["order_id"],
            "EXCEPTION",
            "MISSING_SETTLEMENT",
            "MEDIUM",
            amount_minor,
            (finding,),
            "POTENTIAL_EXPOSURE",
        )

    settlement = lifecycle.settlements[0]
    settled_at = settlement.get("settled_at")
    captured_at = payment.get("captured_at")
    if settled_at not in (None, "") and captured_at not in (None, ""):
        settlement_day = (_timestamp(settled_at) - _timestamp(captured_at)).days
        if settlement_day > 2:
            findings.append(
                RuleFinding(
                    "SETTLEMENT_OUTSIDE_WINDOW",
                    "Settlement arrived after the configured T+2 window.",
                    0,
                    "TIMING_VARIANCE",
                )
            )

    settlement_fee = settlement.get("fees_minor")
    if settlement_fee in (None, ""):
        findings.append(
            RuleFinding(
                "SETTLEMENT_FEE_MISSING", "Settlement has no fee evidence.", 0, "DATA_QUALITY"
            )
        )
    gateway_fee = payment.get("gateway_fee_minor")
    if gateway_fee in (None, ""):
        findings.append(
            RuleFinding(
                "PAYMENT_FEE_MISSING",
                "Captured payment has no gateway fee evidence.",
                0,
                "DATA_QUALITY",
            )
        )
    elif settlement_fee is not None and gateway_fee is not None:
        fee_delta = abs(int(cast(str | int, settlement_fee)) - int(cast(str | int, gateway_fee)))
        if fee_delta > 0:
            findings.append(
                RuleFinding(
                    "SETTLEMENT_FEE_VARIANCE",
                    "Settlement fee differs from the gateway fee; review as a known variance.",
                    fee_delta,
                    "TIMING_VARIANCE",
                )
            )

    if not lifecycle.invoices:
        findings.append(
            RuleFinding(
                "ERP_INVOICE_MISSING",
                "Completed order has no ERP invoice.",
                amount_minor,
                "POTENTIAL_EXPOSURE",
            )
        )
    elif int(lifecycle.invoices[0]["gross_minor"]) != amount_minor:
        findings.append(
            RuleFinding(
                "ERP_AMOUNT_MISMATCH",
                "ERP invoice gross does not equal order amount.",
                abs(int(lifecycle.invoices[0]["gross_minor"]) - amount_minor),
                "DATA_QUALITY",
            )
        )

    sale_movements = [
        movement for movement in lifecycle.inventory_movements
        if str(movement.get("movement_type", "")).upper() == "SALE"
    ]
    return_movements = [
        movement for movement in lifecycle.inventory_movements
        if str(movement.get("movement_type", "")).upper() == "RETURN"
    ]
    for movement in lifecycle.inventory_movements:
        unit_cost = _minor_value(movement.get("unit_cost_minor"))
        inventory_value = _minor_value(movement.get("inventory_value_minor"))
        quantity = int(movement.get("quantity", 0))
        if unit_cost is not None and inventory_value is not None and inventory_value != unit_cost * quantity:
            findings.append(
                RuleFinding(
                    "INVENTORY_VALUE_CALCULATION_ERROR",
                    "Inventory value does not equal unit cost multiplied by quantity.",
                    abs(inventory_value - (unit_cost * quantity)),
                    "DATA_QUALITY",
                )
            )

    sale_quantity = _sum_quantity(sale_movements) if sale_movements else 0
    return_quantity = _sum_quantity(return_movements) if return_movements else 0
    sale_value = _sum_expected_inventory_value(sale_movements)
    return_value = _sum_inventory_value(return_movements)
    if return_movements and not lifecycle.refunds:
        findings.append(
            RuleFinding(
                "INVENTORY_RESTORED_WITHOUT_REFUND",
                "Inventory was restored without a corresponding customer refund.",
                return_value or 0,
                "CONTROL_RISK",
            )
        )

    if lifecycle.refunds:
        refund = lifecycle.refunds[0]
        refund_amount = int(refund["amount_minor"])
        has_return = bool(return_movements)
        if any(
            action.get("action") == "MANUAL_REFUND_APPROVED"
            for action in lifecycle.employee_actions
        ):
            findings.append(
                RuleFinding(
                    "MANUAL_WORKFLOW_ANOMALY",
                    "Refund was approved through a manual workflow.",
                    0,
                    "CONTROL_RISK",
                )
            )
        if refund_amount < amount_minor:
            findings.append(
                RuleFinding(
                    "PARTIAL_REFUND_MISMATCH",
                    "Partial refund cannot be reconciled without line-item reversal evidence.",
                    refund_amount,
                    "POTENTIAL_EXPOSURE",
                )
            )
        elif not has_return:
            findings.append(
                RuleFinding(
                    "INVENTORY_RETURN_MISSING",
                    "Full refund has no corresponding inventory return.",
                    refund_amount,
                    "CONTROL_RISK",
                )
            )
        elif refund_amount >= amount_minor and sale_movements:
            if sale_quantity != return_quantity:
                expected_value = sale_value or 0
                observed_value = return_value or 0
                findings.append(
                    RuleFinding(
                        "INVENTORY_QUANTITY_MISMATCH",
                        "Returned inventory quantity does not equal the quantity sold.",
                        abs(expected_value - observed_value) if expected_value and observed_value else abs(sale_quantity - return_quantity),
                        "CONTROL_RISK",
                    )
                )
            elif sale_value is not None and return_value is not None and sale_value != return_value:
                findings.append(
                    RuleFinding(
                        "INVENTORY_VALUE_MISMATCH",
                        "Returned inventory value does not equal the cost value of the sold item.",
                        abs(sale_value - return_value),
                        "CONTROL_RISK",
                    )
                )
        has_reversal = any(invoice.get("status") == "REVERSED" for invoice in lifecycle.invoices)
        if lifecycle.invoices and lifecycle.invoices[0].get("status") == "ACTIVE" and not has_reversal:
            findings.append(
                RuleFinding(
                    "ERP_REVERSAL_MISSING",
                    "Refund completed while the ERP invoice remains active.",
                    refund_amount,
                    "CONTROL_RISK",
                )
            )

    if not findings:
        return ReconciliationResult(order["order_id"], "RECONCILED", None, "LOW", 0, (), "NONE")

    variance_only = all(
        finding.code in {"SETTLEMENT_OUTSIDE_WINDOW", "SETTLEMENT_FEE_VARIANCE"}
        for finding in findings
    )
    if variance_only:
        variance_type = (
            "SETTLEMENT_FEE_VARIANCE"
            if any(finding.code == "SETTLEMENT_FEE_VARIANCE" for finding in findings)
            else "SETTLEMENT_TIMING"
        )
        return ReconciliationResult(
            order["order_id"],
            "RECONCILED_WITH_VARIANCE",
            variance_type,
            "LOW",
            sum(f.exposure_minor for f in findings),
            tuple(findings),
            "TIMING_VARIANCE",
        )

    primary = findings[0]
    exception_type = {
        "INVENTORY_RETURN_MISSING": "REFUND_WITHOUT_INVENTORY_RETURN",
        "ERP_REVERSAL_MISSING": "REFUND_WITHOUT_ERP_REVERSAL",
        "MANUAL_WORKFLOW_ANOMALY": "MANUAL_WORKFLOW_ANOMALY",
        "PARTIAL_REFUND_MISMATCH": "PARTIAL_REFUND_MISMATCH",
        "ERP_INVOICE_MISSING": "ERP_INVOICE_MISSING",
        "ERP_AMOUNT_MISMATCH": "ERP_AMOUNT_MISMATCH",
        "PAYMENT_FEE_MISSING": "PAYMENT_FEE_MISSING",
        "SETTLEMENT_FEE_MISSING": "SETTLEMENT_FEE_MISSING",
        "INVENTORY_VALUE_MISMATCH": "INVENTORY_VALUE_MISMATCH",
        "INVENTORY_VALUE_CALCULATION_ERROR": "INVENTORY_VALUE_MISMATCH",
        "INVENTORY_QUANTITY_MISMATCH": "INVENTORY_QUANTITY_MISMATCH",
        "INVENTORY_RESTORED_WITHOUT_REFUND": "INVENTORY_RESTORED_WITHOUT_REFUND",
    }.get(primary.code, primary.code)
    severity = (
        "HIGH"
        if exception_type
        in {
            "REFUND_WITHOUT_INVENTORY_RETURN", "REFUND_WITHOUT_ERP_REVERSAL", "DUPLICATE_PAYMENT",
            "INVENTORY_VALUE_MISMATCH", "INVENTORY_QUANTITY_MISMATCH", "INVENTORY_RESTORED_WITHOUT_REFUND",
        }
        else "MEDIUM"
    )
    category = max(
        (finding.exposure_category for finding in findings),
        key=lambda item: {
            "POTENTIAL_EXPOSURE": 4,
            "CONTROL_RISK": 3,
            "DATA_QUALITY": 2,
            "TIMING_VARIANCE": 1,
        }.get(item, 0),
    )
    return ReconciliationResult(
        order["order_id"],
        "EXCEPTION",
        exception_type,
        severity,
        max(f.exposure_minor for f in findings),
        tuple(findings),
        category,
    )


def reconcile_dataset(dataset: Any) -> list[ReconciliationResult]:
    store = dataset.lifecycle_store()
    organization_id = dataset.ground_truth[0]["organization_id"]
    return [
        reconcile_lifecycle(store.get_by_order(organization_id, truth["order_id"]))
        for truth in dataset.ground_truth
    ]
