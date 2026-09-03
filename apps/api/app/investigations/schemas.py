from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InvestigationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    FAILED = "FAILED"


class ProviderHealthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(CONNECTED|UNAVAILABLE|NOT_CONFIGURED)$")
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    configured: bool
    latency_ms: int = Field(ge=0)
    error_category: str | None = Field(default=None, max_length=100)
    retryable: bool | None = None
    detail: str | None = Field(default=None, max_length=500)


class ProviderHealthResponse(ProviderHealthItem):
    """Backward-compatible active-provider fields plus a primary/fallback report."""

    overall_status: str = Field(pattern=r"^(AVAILABLE|DEGRADED|UNAVAILABLE)$")
    active_provider: str | None = Field(default=None, max_length=64)
    providers: list[ProviderHealthItem] = Field(default_factory=list, max_length=4)


class EvidenceSource(StrEnum):
    ORDER = "order"
    PAYMENT = "payment"
    SETTLEMENT = "settlement"
    INVOICE = "invoice"
    REFUND = "refund"
    INVENTORY = "inventory"
    EMPLOYEE_ACTION = "employee_action"


class EvidenceOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    EXISTS = "exists"
    MISSING = "missing"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"


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
    field: str | None = Field(default=None, max_length=100)
    operator: EvidenceOperator | None = None
    expected_value: str | int | float | bool | None = None
    verified: bool = False
    verification_issue: str | None = Field(default=None, max_length=500)


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
    sequence_no: int = Field(default=0, ge=0)
    # Provider tool arguments are bounded JSON, not only scalar query params.
    # Keeping the JSON shape preserves the exact read-only request in the audit trace.
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_record_ids: list[str] = Field(default_factory=list, max_length=100)
    result_summary: str = ""
    provider: str = "unknown"
    model: str = "unknown"


class InvestigationResponse(InvestigationCandidate):
    investigation_id: str
    exception_id: str
    evidence_score: int = Field(ge=0, le=100)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime
    provider: str = "unknown"
    model: str = "unknown"
    prompt_version: str = "v1"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int = Field(default=0, ge=0)
    verifier_passed: bool = False
    verifier_issues: list[str] = Field(default_factory=list, max_length=50)
    rejected_evidence: list[EvidenceItem] = Field(default_factory=list, max_length=30)
    provider_error_category: str | None = Field(default=None, max_length=100)
    provider_retryable: bool | None = None
    failure_stage: str | None = Field(default=None, max_length=100)
    failure_iteration: int | None = Field(default=None, ge=1, le=8)
    failure_detail: str | None = Field(default=None, max_length=500)
    originally_requested_provider: str | None = Field(default=None, max_length=64)
    actual_provider_used: str | None = Field(default=None, max_length=64)
    model_used: str | None = Field(default=None, max_length=128)
    fallback_used: bool = False
    fallback_reason: str | None = Field(default=None, max_length=100)
