from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ExceptionType(StrEnum):
    REFUND_WITHOUT_INVENTORY_RETURN = "REFUND_WITHOUT_INVENTORY_RETURN"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    AMBIGUOUS_ASSOCIATION = "AMBIGUOUS_ASSOCIATION"
    ERP_INVOICE_MISSING = "ERP_INVOICE_MISSING"
    ERP_AMOUNT_MISMATCH = "ERP_AMOUNT_MISMATCH"
    SETTLEMENT_TIMING = "SETTLEMENT_TIMING"
    SETTLEMENT_FEE_VARIANCE = "SETTLEMENT_FEE_VARIANCE"
    MANUAL_WORKFLOW_ANOMALY = "MANUAL_WORKFLOW_ANOMALY"
    REFUND_WITHOUT_ERP_REVERSAL = "REFUND_WITHOUT_ERP_REVERSAL"
    PARTIAL_REFUND_MISMATCH = "PARTIAL_REFUND_MISMATCH"
    PAYMENT_FEE_MISSING = "PAYMENT_FEE_MISSING"
    SETTLEMENT_FEE_MISSING = "SETTLEMENT_FEE_MISSING"
    INVENTORY_VALUE_MISMATCH = "INVENTORY_VALUE_MISMATCH"
    INVENTORY_QUANTITY_MISMATCH = "INVENTORY_QUANTITY_MISMATCH"
    INVENTORY_RESTORED_WITHOUT_REFUND = "INVENTORY_RESTORED_WITHOUT_REFUND"


class ExceptionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    order_id: str
    type: ExceptionType
    severity: Severity
    status: ExceptionStatus
    financial_exposure: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    detected_at: datetime
    rules_triggered: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    organization_id: str
    reconciliation_run_id: str
    lifecycle_count: int = Field(ge=0)
    auto_reconciled_count: int = Field(ge=0)
    exception_count: int = Field(ge=0)
    open_exposure: Decimal = Field(ge=0)
    requires_review_count: int = Field(ge=0)
    generated_at: datetime


class LifecycleResponse(BaseModel):
    organization_id: str
    order: dict[str, Any]
    payments: list[dict[str, Any]]
    settlements: list[dict[str, Any]]
    invoices: list[dict[str, Any]]
    refunds: list[dict[str, Any]]
    inventory_movements: list[dict[str, Any]]
    employee_actions: list[dict[str, Any]]
