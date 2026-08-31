from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InvestigationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    FAILED = "FAILED"


class EvidenceSource(StrEnum):
    ORDER = "order"
    PAYMENT = "payment"
    SETTLEMENT = "settlement"
    INVOICE = "invoice"
    REFUND = "refund"
    INVENTORY = "inventory"
    EMPLOYEE_ACTION = "employee_action"


class RootCauseCode(StrEnum):
    SETTLEMENT_TIMING = "SETTLEMENT_TIMING"
    SETTLEMENT_FEE_VARIANCE = "SETTLEMENT_FEE_VARIANCE"
    SETTLEMENT_MISSING = "SETTLEMENT_MISSING"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    ERP_INVOICE_MISSING = "ERP_INVOICE_MISSING"
    ERP_AMOUNT_MISMATCH = "ERP_AMOUNT_MISMATCH"
    INCOMPLETE_REFUND_WORKFLOW = "INCOMPLETE_REFUND_WORKFLOW"
    INVENTORY_REVERSAL_MISSING = "INVENTORY_REVERSAL_MISSING"
    ERP_REVERSAL_MISSING = "ERP_REVERSAL_MISSING"
    REFERENCE_MAPPING_FAILURE = "REFERENCE_MAPPING_FAILURE"
    PARTIAL_REFUND_MISMATCH = "PARTIAL_REFUND_MISMATCH"
    PAYMENT_FEE_MISSING = "PAYMENT_FEE_MISSING"
    SETTLEMENT_FEE_MISSING = "SETTLEMENT_FEE_MISSING"
    DATA_QUALITY_ERROR = "DATA_QUALITY_ERROR"
    AMBIGUOUS_ASSOCIATION = "AMBIGUOUS_ASSOCIATION"
    UNKNOWN = "UNKNOWN"


class RecommendationCode(StrEnum):
    REQUEST_INVENTORY_VERIFICATION = "REQUEST_INVENTORY_VERIFICATION"
    REQUEST_ERP_REVERSAL_REVIEW = "REQUEST_ERP_REVERSAL_REVIEW"
    REQUEST_PAYMENT_REVIEW = "REQUEST_PAYMENT_REVIEW"
    REQUEST_MANUAL_REVIEW = "REQUEST_MANUAL_REVIEW"


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: EvidenceSource
    record_id: str | None = Field(default=None, min_length=1, max_length=100)
    fact: str = Field(min_length=1, max_length=500)


class InvestigationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: InvestigationStatus
    root_cause_code: RootCauseCode | None = None
    summary: str = Field(min_length=1, max_length=1000)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    contradictory_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    missing_evidence: list[str] = Field(default_factory=list, max_length=20)
    recommended_action_code: RecommendationCode | None = None
    requires_human_review: bool = True


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=30)
    duration_ms: int = Field(ge=0)
    evidence: list[EvidenceItem] = Field(default_factory=list, max_length=50)


class InvestigationResponse(InvestigationCandidate):
    investigation_id: str
    exception_id: str
    evidence_score: int = Field(ge=0, le=100)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime
