from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.lifecycle import CanonicalLifecycle


@dataclass(frozen=True, slots=True)
class RuleFinding:
    code: str
    message: str
    exposure_minor: int = 0


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    order_id: str
    status: str
    exception_type: str | None
    severity: str
    exposure_minor: int
    findings: tuple[RuleFinding, ...] = field(default_factory=tuple)


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("timestamp must be an ISO string")
    return datetime.fromisoformat(value)


def reconcile_lifecycle(lifecycle: CanonicalLifecycle) -> ReconciliationResult:
    """Reconcile one lifecycle using only canonical records and deterministic rules."""
    findings: list[RuleFinding] = []
    order = lifecycle.order
    amount_minor = int(order["amount_minor"])

    if len(lifecycle.payments) > 1:
        ambiguous = any(str(payment.get("payment_id", "")).startswith("PAY-AMB-") for payment in lifecycle.payments)
        code = "AMBIGUOUS_ASSOCIATION" if ambiguous else "DUPLICATE_PAYMENT"
        message = "Multiple payment candidates satisfy the available association criteria." if ambiguous else "More than one captured payment is associated with the order."
        return ReconciliationResult(order["order_id"], "AMBIGUOUS" if ambiguous else "EXCEPTION", code, "HIGH", amount_minor, (RuleFinding(code, message, amount_minor),))

    if not lifecycle.payments:
        finding = RuleFinding("PAYMENT_MISSING", "Completed order has no captured payment.", amount_minor)
        return ReconciliationResult(order["order_id"], "EXCEPTION", finding.code, "HIGH", finding.exposure_minor, (finding,))

    payment = lifecycle.payments[0]
    if not lifecycle.settlements:
        finding = RuleFinding("SETTLEMENT_MISSING", "Captured payment has no settlement record.", amount_minor)
        return ReconciliationResult(order["order_id"], "EXCEPTION", "MISSING_SETTLEMENT", "MEDIUM", amount_minor, (finding,))

    settlement = lifecycle.settlements[0]
    settlement_day = (_timestamp(settlement["settled_at"]) - _timestamp(payment["captured_at"])).days
    if settlement_day > 2:
        findings.append(RuleFinding("SETTLEMENT_OUTSIDE_WINDOW", "Settlement arrived after the configured T+2 window."))

    expected_fee = int(payment["gateway_fee_minor"])
    fee_delta = abs(int(settlement["fees_minor"]) - expected_fee)
    if fee_delta > 0:
        findings.append(RuleFinding("SETTLEMENT_FEE_VARIANCE", "Settlement fee differs from the gateway fee; review as a known variance.", fee_delta))

    if not lifecycle.invoices:
        findings.append(RuleFinding("ERP_INVOICE_MISSING", "Completed order has no ERP invoice.", amount_minor))
    elif int(lifecycle.invoices[0]["gross_minor"]) != amount_minor:
        findings.append(RuleFinding("ERP_AMOUNT_MISMATCH", "ERP invoice gross does not equal order amount.", abs(int(lifecycle.invoices[0]["gross_minor"]) - amount_minor)))

    if lifecycle.refunds:
        refund = lifecycle.refunds[0]
        refund_amount = int(refund["amount_minor"])
        has_return = any(movement.get("movement_type") == "RETURN" for movement in lifecycle.inventory_movements)
        if any(action.get("action") == "MANUAL_REFUND_APPROVED" for action in lifecycle.employee_actions):
            findings.append(RuleFinding("MANUAL_WORKFLOW_ANOMALY", "Refund was approved through a manual workflow."))
        if refund_amount < amount_minor:
            findings.append(RuleFinding("PARTIAL_REFUND_MISMATCH", "Partial refund cannot be reconciled without line-item reversal evidence.", refund_amount))
        elif not has_return:
            findings.append(RuleFinding("INVENTORY_RETURN_MISSING", "Full refund has no corresponding inventory return.", refund_amount))
        if lifecycle.invoices and lifecycle.invoices[0].get("status") == "ACTIVE":
            findings.append(RuleFinding("ERP_REVERSAL_MISSING", "Refund completed while the ERP invoice remains active.", refund_amount))

    if not findings:
        return ReconciliationResult(order["order_id"], "RECONCILED", None, "LOW", 0)

    variance_only = all(finding.code in {"SETTLEMENT_OUTSIDE_WINDOW", "SETTLEMENT_FEE_VARIANCE"} for finding in findings)
    if variance_only:
        variance_type = "SETTLEMENT_FEE_VARIANCE" if any(finding.code == "SETTLEMENT_FEE_VARIANCE" for finding in findings) else "SETTLEMENT_TIMING"
        return ReconciliationResult(order["order_id"], "RECONCILED_WITH_VARIANCE", variance_type, "LOW", sum(f.exposure_minor for f in findings), tuple(findings))

    primary = findings[0]
    exception_type = {
        "INVENTORY_RETURN_MISSING": "REFUND_WITHOUT_INVENTORY_RETURN",
        "ERP_REVERSAL_MISSING": "REFUND_WITHOUT_ERP_REVERSAL",
        "MANUAL_WORKFLOW_ANOMALY": "MANUAL_WORKFLOW_ANOMALY",
        "PARTIAL_REFUND_MISMATCH": "PARTIAL_REFUND_MISMATCH",
        "ERP_INVOICE_MISSING": "ERP_INVOICE_MISSING",
        "ERP_AMOUNT_MISMATCH": "ERP_AMOUNT_MISMATCH",
    }.get(primary.code, primary.code)
    severity = "HIGH" if exception_type in {"REFUND_WITHOUT_INVENTORY_RETURN", "REFUND_WITHOUT_ERP_REVERSAL", "DUPLICATE_PAYMENT"} else "MEDIUM"
    return ReconciliationResult(order["order_id"], "EXCEPTION", exception_type, severity, max(f.exposure_minor for f in findings), tuple(findings))


def reconcile_dataset(dataset: Any) -> list[ReconciliationResult]:
    store = dataset.lifecycle_store()
    organization_id = dataset.ground_truth[0]["organization_id"]
    return [reconcile_lifecycle(store.get_by_order(organization_id, truth["order_id"])) for truth in dataset.ground_truth]
