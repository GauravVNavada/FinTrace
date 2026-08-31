from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    ANALYST = "ANALYST"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    CONTROLLER = "CONTROLLER"
    AUDITOR = "AUDITOR"


class Capability(StrEnum):
    FINANCIAL_INVESTIGATION_READ = "financial_investigation.read"
    FINANCIAL_INVESTIGATION_WRITE = "financial_investigation.write"
    EXCEPTION_READ = "exception.read"
    EXCEPTION_INVESTIGATE = "exception.investigate"
    EXCEPTION_COMMENT = "exception.comment"
    RESOLUTION_REQUEST = "resolution.request"
    RESOLUTION_APPROVE_LOW = "resolution.approve.low"
    RESOLUTION_APPROVE_HIGH = "resolution.approve.high"
    AUDIT_READ = "audit.read"
    POLICY_MANAGE = "policy.manage"
    ANALYTICS_READ = "analytics.read"


class ActionCode(StrEnum):
    REQUEST_INVENTORY_VERIFICATION = "REQUEST_INVENTORY_VERIFICATION"
    REQUEST_ERP_INVOICE_CORRECTION = "REQUEST_ERP_INVOICE_CORRECTION"
    REQUEST_PAYMENT_REVIEW = "REQUEST_PAYMENT_REVIEW"
    REQUEST_SETTLEMENT_REVIEW = "REQUEST_SETTLEMENT_REVIEW"
    REQUEST_REFUND_REVIEW = "REQUEST_REFUND_REVIEW"
    MARK_AS_TIMING_DIFFERENCE = "MARK_AS_TIMING_DIFFERENCE"
    MARK_AS_EXPECTED_FEE_VARIANCE = "MARK_AS_EXPECTED_FEE_VARIANCE"
    ESCALATE_TO_FINANCE_MANAGER = "ESCALATE_TO_FINANCE_MANAGER"
    ESCALATE_TO_CONTROLLER = "ESCALATE_TO_CONTROLLER"
    CLOSE_AS_RESOLVED = "CLOSE_AS_RESOLVED"


class ApprovalStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Decision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActorContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1, max_length=64)
    actor_id: str = Field(min_length=1, max_length=128)
    role: Role

    @property
    def capabilities(self) -> frozenset[Capability]:
        capabilities = {
            Capability.FINANCIAL_INVESTIGATION_READ,
            Capability.FINANCIAL_INVESTIGATION_WRITE,
            Capability.EXCEPTION_READ,
            Capability.EXCEPTION_INVESTIGATE,
            Capability.EXCEPTION_COMMENT,
            Capability.RESOLUTION_REQUEST,
        }
        if self.role == Role.FINANCE_MANAGER:
            capabilities.update({Capability.RESOLUTION_APPROVE_LOW, Capability.AUDIT_READ})
        elif self.role == Role.CONTROLLER:
            capabilities.update(
                {
                    Capability.RESOLUTION_APPROVE_LOW,
                    Capability.RESOLUTION_APPROVE_HIGH,
                    Capability.POLICY_MANAGE,
                    Capability.ANALYTICS_READ,
                    Capability.AUDIT_READ,
                }
            )
        elif self.role == Role.AUDITOR:
            capabilities = {
                Capability.FINANCIAL_INVESTIGATION_READ,
                Capability.EXCEPTION_READ,
                Capability.AUDIT_READ,
            }
        return frozenset(capabilities)


class ResolutionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_code: ActionCode


class ResolutionRequestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    exception_id: str
    action_code: ActionCode
    status: ApprovalStatus
    financial_exposure: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    required_capability: Capability
    required_approvals: int = Field(ge=1, le=2)
    approvals_received: int = Field(ge=0, le=2)
    requester_id: str
    created_at: datetime


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    request_id: str
    decision: Decision
    request_status: ApprovalStatus
    required_approvals: int = Field(ge=1, le=2)
    approvals_received: int = Field(ge=0, le=2)
    actor_id: str
    decided_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    organization_id: str
    actor_id: str
    action: str
    resource_id: str
    correlation_id: str
    created_at: datetime
