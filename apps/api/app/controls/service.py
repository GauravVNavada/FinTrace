import json
from datetime import UTC, datetime
from decimal import Decimal
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
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
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
        self._request_idempotency: dict[
            tuple[str, str], tuple[str, ActionCode, ResolutionRequestResponse]
        ] = {}
        self._approval_idempotency: dict[tuple[str, str], ApprovalResponse] = {}

    def request_resolution(
        self, context: ActorContext, exception_id: str, action: ActionCode, idempotency_key: str
    ) -> ResolutionRequestResponse:
        self._require(context, Capability.RESOLUTION_REQUEST)
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (context.organization_id, idempotency_key)
        with self._lock:
            exception = self._repository.get_exception(context.organization_id, exception_id)
            if exception is None:
                raise ControlNotFoundError(exception_id)
            return self._create_resolution_request(context, exception, action, idempotency_key, key)

    def request_financial_resolution(
        self,
        context: ActorContext,
        investigation_id: str,
        run_id: str,
        result_id: str,
        action: ActionCode,
        idempotency_key: str,
    ) -> ResolutionRequestResponse:
        """Create a controlled review request for an uploaded reconciliation result."""
        self._require(context, Capability.RESOLUTION_REQUEST)
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        result = self._repository.get_reconciliation_result(
            context.organization_id, investigation_id, run_id, result_id
        )
        run = self._repository.latest_reconciliation_run(context.organization_id, investigation_id)
        financial_investigation = self._repository.get_financial_investigation(
            context.organization_id, investigation_id
        )
        if (
            result is None
            or run is None
            or str(run.get("id")) != run_id
            or financial_investigation is None
        ):
            raise ControlNotFoundError(result_id)
        if result.get("status") not in {"EXCEPTION", "AMBIGUOUS"} or not result.get(
            "exception_type"
        ):
            raise ControlStateError("Only exception or ambiguous results can be sent for review")
        try:
            exception = ExceptionSummary(
                id=str(result_id),
                organization_id=context.organization_id,
                order_id=str(result["order_id"]),
                type=ExceptionType(str(result["exception_type"])),
                severity=Severity(str(result.get("severity", "MEDIUM"))),
                status=ExceptionStatus.OPEN,
                financial_exposure=Decimal(int(result.get("exposure_minor", 0))) / Decimal(100),
                currency=str(financial_investigation["base_currency"]),
                detected_at=datetime.now(UTC),
                rules_triggered=[str(item.get("code")) for item in result.get("findings", [])],
            )
        except (KeyError, ValueError) as error:
            raise ControlStateError(
                "The uploaded result has an unsupported exception type or severity"
            ) from error
        key = (context.organization_id, idempotency_key)
        with self._lock:
            response = self._create_resolution_request(
                context, exception, action, idempotency_key, key
            )
            return response

    def _create_resolution_request(
        self,
        context: ActorContext,
        exception: ExceptionSummary,
        action: ActionCode,
        idempotency_key: str,
        key: tuple[str, str],
    ) -> ResolutionRequestResponse:
        request_hash = self._request_hash(exception.id, action)
        if self._durable:
            previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
            if previous is not None:
                if previous["request_hash"] != request_hash:
                    raise ControlConflictError(
                        "Idempotency-Key was already used for another request"
                    )
                if int(previous.get("response_status", 425)) == 425:
                    raise ControlConflictError(
                        "An identical approval request is already in progress"
                    )
                return ResolutionRequestResponse.model_validate(previous["response_body"])
        previous = self._request_idempotency.get(key)
        if previous is not None:
            previous_exception_id, previous_action, response = previous
            if previous_exception_id != exception.id or previous_action != action:
                raise ControlConflictError("Idempotency-Key was already used for another request")
            return response
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
        if self._durable:
            body = response.model_dump(mode="json")
            reserved = self._repository.reserve_idempotency(
                context.organization_id, context.actor_id, idempotency_key, request_hash
            )
            if reserved is not None:
                if reserved.get("request_hash") != request_hash:
                    raise ControlConflictError(
                        "Idempotency-Key was already used for another request"
                    )
                if int(reserved.get("response_status", 425)) == 425:
                    raise ControlConflictError(
                        "An identical approval request is already in progress"
                    )
                return ResolutionRequestResponse.model_validate(reserved["response_body"])
            try:
                self._repository.save_resolution_request(context.organization_id, body)
            except Exception:
                self._repository.release_idempotency(context.organization_id, idempotency_key)
                raise
            self._repository.complete_idempotency(
                context.organization_id, idempotency_key, 200, body
            )
        self._requests[response.request_id] = (context.organization_id, response, set())
        self._request_idempotency[key] = (exception.id, action, response)
        self._repository.record_audit_event(
            context.organization_id, "APPROVAL_REQUESTED", response.request_id, context.actor_id
        )
        return response

    def approve(
        self, context: ActorContext, request_id: str, idempotency_key: str
    ) -> ApprovalResponse:
        return self._decide(context, request_id, idempotency_key, Decision.APPROVED)

    def reject(
        self, context: ActorContext, request_id: str, idempotency_key: str
    ) -> ApprovalResponse:
        return self._decide(context, request_id, idempotency_key, Decision.REJECTED)

    def _decide(
        self, context: ActorContext, request_id: str, idempotency_key: str, decision: Decision
    ) -> ApprovalResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        with self._lock:
            if self._durable:
                request_record = self._repository.get_resolution_request(
                    context.organization_id, request_id
                )
                if request_record is None:
                    raise ControlNotFoundError(request_id)
                response = ResolutionRequestResponse.model_validate(
                    {key: value for key, value in request_record.items() if key != "approver_ids"}
                )
                approvers = {str(actor_id) for actor_id in request_record.get("approver_ids", [])}
                approval_hash = self._approval_hash(request_id, decision)
                previous = self._repository.get_idempotency(
                    context.organization_id, idempotency_key
                )
                if previous is not None:
                    if previous["request_hash"] != approval_hash:
                        raise ControlConflictError(
                            "Idempotency-Key was already used for another approval"
                        )
                    if int(previous.get("response_status", 425)) == 425:
                        raise ControlConflictError(
                            "An identical approval decision is already in progress"
                        )
                    return ApprovalResponse.model_validate(previous["response_body"])
                self._validate_decision(context, response, approvers)
                now = datetime.now(UTC)
                approval_id = f"APR-{uuid4().hex[:12].upper()}"
                applied = self._repository.apply_approval_decision(
                    context.organization_id,
                    request_id,
                    context.actor_id,
                    decision.value,
                    approval_id,
                    now.isoformat(),
                )
                if applied is None:
                    raise ControlNotFoundError(request_id)
                if not applied.get("applied"):
                    reason = applied.get("reason")
                    if reason == "duplicate":
                        raise ControlStateError("An actor can approve a request only once")
                    raise ControlStateError("Approval request is no longer pending")
                updated_status = ApprovalStatus(str(applied["status"]))
                approvals_received = int(applied["approvals_received"])
                approval = ApprovalResponse(
                    approval_id=approval_id,
                    request_id=request_id,
                    decision=decision,
                    request_status=updated_status,
                    required_approvals=response.required_approvals,
                    approvals_received=approvals_received,
                    actor_id=context.actor_id,
                    decided_at=now,
                )
                self._repository.put_idempotency(
                    context.organization_id,
                    context.actor_id,
                    idempotency_key,
                    approval_hash,
                    200,
                    approval.model_dump(mode="json"),
                )
                self._repository.record_audit_event(
                    context.organization_id,
                    "APPROVAL_GRANTED" if decision == Decision.APPROVED else "APPROVAL_REJECTED",
                    request_id,
                    context.actor_id,
                )
                return approval
            request = self._requests.get(request_id)
            if request is None or request[0] != context.organization_id:
                raise ControlNotFoundError(request_id)
            _, response, approvers = request
            if context.role not in {"FINANCE_MANAGER", "CONTROLLER"}:
                raise ControlForbiddenError("Actor cannot approve or reject remediation")
            if response.required_capability not in context.capabilities:
                raise ControlForbiddenError("Actor lacks the required approval capability")
            if context.actor_id == response.requester_id:
                raise ControlForbiddenError("The requester cannot approve their own request")
            approval_key = (context.organization_id, idempotency_key)
            previous = self._approval_idempotency.get(approval_key)
            if previous is not None:
                if previous.request_id != request_id or previous.decision != decision:
                    raise ControlConflictError(
                        "Idempotency-Key was already used for another approval"
                    )
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
                updated_status = (
                    ApprovalStatus.APPROVED
                    if approvals_received >= response.required_approvals
                    else ApprovalStatus.PENDING_APPROVAL
                )
            updated_request = response.model_copy(
                update={"status": updated_status, "approvals_received": approvals_received}
            )
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
        return sha256(
            json.dumps(
                {"exception_id": exception_id, "action_code": action.value}, sort_keys=True
            ).encode()
        ).hexdigest()

    @staticmethod
    def _approval_hash(request_id: str, decision: Decision) -> str:
        return sha256(
            json.dumps(
                {"request_id": request_id, "decision": decision.value}, sort_keys=True
            ).encode()
        ).hexdigest()

    @staticmethod
    def _validate_decision(
        context: ActorContext, response: ResolutionRequestResponse, approvers: set[str]
    ) -> None:
        if context.role not in {"FINANCE_MANAGER", "CONTROLLER"}:
            raise ControlForbiddenError("Actor cannot approve or reject remediation")
        if response.required_capability not in context.capabilities:
            raise ControlForbiddenError("Actor lacks the required approval capability")
        if context.actor_id == response.requester_id:
            raise ControlForbiddenError("The requester cannot approve their own request")

    @staticmethod
    def _require(context: ActorContext, capability: Capability) -> None:
        if capability not in context.capabilities:
            raise ControlForbiddenError("Actor lacks the required capability")
