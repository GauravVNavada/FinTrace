import json
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any
from uuid import uuid4

from app.controls.policy import action_allowed, approval_plan
from app.controls.schemas import (
    ActionCode,
    ActorContext,
    ApprovalResponse,
    ApprovalStatus,
    Capability,
    Decision,
    ResolutionRequestResponse,
)
from app.repositories.contracts import LifecycleRepository


class ControlNotFoundError(LookupError):
    pass


class ControlForbiddenError(PermissionError):
    pass


class ControlConflictError(ValueError):
    pass


class ControlStateError(ValueError):
    pass


class ControlsService:
    def __init__(self, repository: LifecycleRepository) -> None:
        self._repository: Any = repository
        self._lock = RLock()
        self._requests: dict[str, tuple[str, ResolutionRequestResponse, set[str]]] = {}
        self._request_idempotency: dict[tuple[str, str], tuple[str, ActionCode, ResolutionRequestResponse]] = {}
        self._approval_idempotency: dict[tuple[str, str], ApprovalResponse] = {}

    def request_resolution(self, context: ActorContext, exception_id: str, action: ActionCode, idempotency_key: str) -> ResolutionRequestResponse:
        self._require(context, Capability.RESOLUTION_REQUEST)
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (context.organization_id, idempotency_key)
        with self._lock:
            if self._durable:
                request_hash = self._request_hash(exception_id, action)
                previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
                if previous is not None:
                    if previous["request_hash"] != request_hash:
                        raise ControlConflictError("Idempotency-Key was already used for another request")
                    return ResolutionRequestResponse.model_validate(previous["response_body"])
            previous = self._request_idempotency.get(key)
            if previous is not None:
                previous_exception_id, previous_action, response = previous
                if previous_exception_id != exception_id or previous_action != action:
                    raise ControlConflictError("Idempotency-Key was already used for another request")
                return response
            exception = self._repository.get_exception(context.organization_id, exception_id)
            if exception is None:
                raise ControlNotFoundError(exception_id)
            if not action_allowed(exception, action):
                raise ControlForbiddenError("Action is not allowed for this exception type")
            plan = approval_plan(exception)
            response = ResolutionRequestResponse(
                request_id=f"REQ-{uuid4().hex[:12].upper()}",
                exception_id=exception.id,
                action_code=action,
                status=ApprovalStatus.PENDING_APPROVAL,
                financial_exposure=exception.financial_exposure,
                currency=exception.currency,
                required_capability=plan.required_capability,
                required_approvals=plan.required_approvals,
                approvals_received=0,
                requester_id=context.actor_id,
                created_at=datetime.now(UTC),
            )
            self._requests[response.request_id] = (context.organization_id, response, set())
            self._request_idempotency[key] = (exception_id, action, response)
            if self._durable:
                body = response.model_dump(mode="json")
                self._repository.save_resolution_request(context.organization_id, body)
                self._repository.put_idempotency(context.organization_id, context.actor_id, idempotency_key, self._request_hash(exception_id, action), 200, body)
            self._repository.record_audit_event(context.organization_id, "APPROVAL_REQUESTED", response.request_id, context.actor_id)
            return response

    def approve(self, context: ActorContext, request_id: str, idempotency_key: str) -> ApprovalResponse:
        return self._decide(context, request_id, idempotency_key, Decision.APPROVED)

    def reject(self, context: ActorContext, request_id: str, idempotency_key: str) -> ApprovalResponse:
        return self._decide(context, request_id, idempotency_key, Decision.REJECTED)

    def _decide(self, context: ActorContext, request_id: str, idempotency_key: str, decision: Decision) -> ApprovalResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        with self._lock:
            if self._durable:
                request_record = self._repository.get_resolution_request(context.organization_id, request_id)
                if request_record is None:
                    raise ControlNotFoundError(request_id)
                response = ResolutionRequestResponse.model_validate({key: value for key, value in request_record.items() if key != "approver_ids"})
                approvers = {str(actor_id) for actor_id in request_record.get("approver_ids", [])}
                approval_hash = self._approval_hash(request_id, decision)
                previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
                if previous is not None:
                    if previous["request_hash"] != approval_hash:
                        raise ControlConflictError("Idempotency-Key was already used for another approval")
                    return ApprovalResponse.model_validate(previous["response_body"])
                self._validate_decision(context, response, approvers)
                if response.status != ApprovalStatus.PENDING_APPROVAL:
                    raise ControlStateError("Approval request is no longer pending")
                if context.actor_id in approvers:
                    raise ControlStateError("An actor can approve a request only once")
                now = datetime.now(UTC)
                if decision == Decision.REJECTED:
                    updated_status = ApprovalStatus.REJECTED
                    approvals_received = len(approvers)
                else:
                    approvals_received = len(approvers) + 1
                    updated_status = ApprovalStatus.APPROVED if approvals_received >= response.required_approvals else ApprovalStatus.PENDING_APPROVAL
                updated_request = response.model_copy(update={"status": updated_status, "approvals_received": approvals_received})
                approval = ApprovalResponse(
                    approval_id=f"APR-{uuid4().hex[:12].upper()}", request_id=request_id, decision=decision,
                    request_status=updated_status, required_approvals=updated_request.required_approvals,
                    approvals_received=approvals_received, actor_id=context.actor_id, decided_at=now,
                )
                if not self._repository.save_approval_decision(context.organization_id, request_id, context.actor_id, decision.value, approval.approval_id, now.isoformat()):
                    raise ControlStateError("An actor can approve a request only once")
                self._repository.update_resolution_request(context.organization_id, updated_request.model_dump(mode="json"))
                self._repository.put_idempotency(context.organization_id, context.actor_id, idempotency_key, approval_hash, 200, approval.model_dump(mode="json"))
                self._repository.record_audit_event(context.organization_id, "APPROVAL_GRANTED" if decision == Decision.APPROVED else "APPROVAL_REJECTED", request_id, context.actor_id)
                return approval
            request = self._requests.get(request_id)
            if request is None or request[0] != context.organization_id:
                raise ControlNotFoundError(request_id)
            _, response, approvers = request
            if context.role not in {"FINANCE_MANAGER", "CONTROLLER"}:
                raise ControlForbiddenError("Actor cannot approve or reject remediation")
            if response.required_capability not in context.capabilities:
                raise ControlForbiddenError("Actor lacks the required approval capability")
            approval_key = (context.organization_id, idempotency_key)
            previous = self._approval_idempotency.get(approval_key)
            if previous is not None:
                if previous.request_id != request_id or previous.decision != decision:
                    raise ControlConflictError("Idempotency-Key was already used for another approval")
                return previous
            if response.status != ApprovalStatus.PENDING_APPROVAL:
                raise ControlStateError("Approval request is no longer pending")
            if context.actor_id in approvers:
                raise ControlStateError("An actor can approve a request only once")
            now = datetime.now(UTC)
            if decision == Decision.REJECTED:
                updated_status = ApprovalStatus.REJECTED
                approvals_received = len(approvers)
            else:
                approvers.add(context.actor_id)
                approvals_received = len(approvers)
                updated_status = ApprovalStatus.APPROVED if approvals_received >= response.required_approvals else ApprovalStatus.PENDING_APPROVAL
            updated_request = response.model_copy(update={"status": updated_status, "approvals_received": approvals_received})
            self._requests[request_id] = (context.organization_id, updated_request, approvers)
            approval = ApprovalResponse(
                approval_id=f"APR-{uuid4().hex[:12].upper()}",
                request_id=request_id,
                decision=decision,
                request_status=updated_status,
                required_approvals=updated_request.required_approvals,
                approvals_received=approvals_received,
                actor_id=context.actor_id,
                decided_at=now,
            )
            self._approval_idempotency[approval_key] = approval
            self._repository.record_audit_event(
                context.organization_id,
                "APPROVAL_GRANTED" if decision == Decision.APPROVED else "APPROVAL_REJECTED",
                request_id,
                context.actor_id,
            )
            return approval

    @property
    def _durable(self) -> bool:
        return getattr(self._repository, "supports_workflow_persistence", False) is True

    @staticmethod
    def _request_hash(exception_id: str, action: ActionCode) -> str:
        return sha256(json.dumps({"exception_id": exception_id, "action_code": action.value}, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _approval_hash(request_id: str, decision: Decision) -> str:
        return sha256(json.dumps({"request_id": request_id, "decision": decision.value}, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _validate_decision(context: ActorContext, response: ResolutionRequestResponse, approvers: set[str]) -> None:
        if context.role not in {"FINANCE_MANAGER", "CONTROLLER"}:
            raise ControlForbiddenError("Actor cannot approve or reject remediation")
        if response.required_capability not in context.capabilities:
            raise ControlForbiddenError("Actor lacks the required approval capability")

    @staticmethod
    def _require(context: ActorContext, capability: Capability) -> None:
        if capability not in context.capabilities:
            raise ControlForbiddenError("Actor lacks the required capability")
