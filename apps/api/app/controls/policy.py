from dataclasses import dataclass
from decimal import Decimal

from app.controls.schemas import ActionCode, Capability
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType


@dataclass(frozen=True, slots=True)
class ApprovalPlan:
    required_capability: Capability
    required_approvals: int


_LOW_VALUE_LIMIT = Decimal(10000)
_HIGH_VALUE_LIMIT = Decimal(100000)


def approval_plan(exception: ExceptionSummary) -> ApprovalPlan:
    if exception.type in {
        ExceptionType.DUPLICATE_PAYMENT,
        ExceptionType.AMBIGUOUS_ASSOCIATION,
    } or exception.status in {ExceptionStatus.ESCALATED}:
        return ApprovalPlan(Capability.RESOLUTION_APPROVE_HIGH, 1)
    if exception.financial_exposure <= _LOW_VALUE_LIMIT:
        return ApprovalPlan(Capability.RESOLUTION_APPROVE_LOW, 1)
    if exception.financial_exposure <= _HIGH_VALUE_LIMIT:
        return ApprovalPlan(Capability.RESOLUTION_APPROVE_HIGH, 1)
    return ApprovalPlan(Capability.RESOLUTION_APPROVE_HIGH, 2)


def action_allowed(exception: ExceptionSummary, action: ActionCode) -> bool:
    allowed: dict[ExceptionType, set[ActionCode]] = {
        ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN: {
            ActionCode.REQUEST_INVENTORY_VERIFICATION,
            ActionCode.REQUEST_REFUND_REVIEW,
            ActionCode.ESCALATE_TO_CONTROLLER,
        },
        ExceptionType.REFUND_WITHOUT_ERP_REVERSAL: {
            ActionCode.REQUEST_ERP_INVOICE_CORRECTION,
            ActionCode.REQUEST_REFUND_REVIEW,
            ActionCode.ESCALATE_TO_CONTROLLER,
        },
        ExceptionType.DUPLICATE_PAYMENT: {
            ActionCode.REQUEST_PAYMENT_REVIEW,
            ActionCode.REQUEST_REFUND_REVIEW,
            ActionCode.REQUEST_SETTLEMENT_REVIEW,
            ActionCode.ESCALATE_TO_CONTROLLER,
        },
        ExceptionType.AMBIGUOUS_ASSOCIATION: {
            ActionCode.REQUEST_PAYMENT_REVIEW,
            ActionCode.ESCALATE_TO_CONTROLLER,
        },
        ExceptionType.MISSING_SETTLEMENT: {
            ActionCode.REQUEST_SETTLEMENT_REVIEW,
            ActionCode.MARK_AS_TIMING_DIFFERENCE,
        },
        ExceptionType.ERP_INVOICE_MISSING: {ActionCode.REQUEST_ERP_INVOICE_CORRECTION},
        ExceptionType.ERP_AMOUNT_MISMATCH: {ActionCode.REQUEST_ERP_INVOICE_CORRECTION},
        ExceptionType.SETTLEMENT_TIMING: {
            ActionCode.MARK_AS_TIMING_DIFFERENCE,
            ActionCode.REQUEST_SETTLEMENT_REVIEW,
        },
        ExceptionType.SETTLEMENT_FEE_VARIANCE: {
            ActionCode.MARK_AS_EXPECTED_FEE_VARIANCE,
            ActionCode.REQUEST_SETTLEMENT_REVIEW,
        },
        ExceptionType.MANUAL_WORKFLOW_ANOMALY: {
            ActionCode.ESCALATE_TO_FINANCE_MANAGER,
            ActionCode.ESCALATE_TO_CONTROLLER,
        },
    }
    return action in allowed.get(
        exception.type, {ActionCode.REQUEST_REFUND_REVIEW, ActionCode.ESCALATE_TO_CONTROLLER}
    )
