import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.domain.lifecycle import LifecycleNotFoundError
from app.domain.schemas import ExceptionSummary, ExceptionType
from app.investigations.provider import AIClient, ProviderUnavailable
from app.investigations.schemas import (
    EvidenceItem,
    InvestigationCandidate,
    InvestigationResponse,
    InvestigationStatus,
    RecommendationCode,
    RootCauseCode,
    ToolCall,
)
from app.investigations.tools import EvidenceToolRegistry
from app.investigations.verifier import verify_candidate
from app.repositories.contracts import LifecycleRepository

_logger = logging.getLogger("fintrace.investigation")


class InvestigationNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class InvestigationService:
    def __init__(self, repository: LifecycleRepository, provider: AIClient) -> None:
        self._repository: Any = repository
        self._provider = provider
        self._tools = EvidenceToolRegistry(repository)
        self._lock = RLock()
        self._results: dict[str, tuple[str, InvestigationResponse]] = {}
        self._idempotency: dict[tuple[str, str], tuple[str, InvestigationResponse]] = {}

    def start(
        self, organization_id: str, exception_id: str, idempotency_key: str
    ) -> InvestigationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (organization_id, idempotency_key)
        request_hash = self._request_hash(exception_id)
        with self._lock:
            if self._durable:
                previous = self._repository.get_idempotency(organization_id, idempotency_key)
                if previous is not None:
                    if previous["request_hash"] != request_hash:
                        raise IdempotencyConflictError(
                            "Idempotency-Key was already used for another exception"
                        )
                    if int(previous.get("response_status", 425)) == 425:
                        raise IdempotencyConflictError(
                            "An identical investigation is already in progress"
                        )
                    return InvestigationResponse.model_validate(previous["response_body"])
            previous = self._idempotency.get(key)
            if previous is not None:
                previous_exception_id, response = previous
                if previous_exception_id != exception_id:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used for another exception"
                    )
                return response

            exception = self._repository.get_exception(organization_id, exception_id)
            if exception is None:
                raise InvestigationNotFoundError(exception_id)
            if self._durable:
                reserved = self._repository.reserve_idempotency(
                    organization_id, "system", idempotency_key, request_hash
                )
                if reserved is not None:
                    if reserved["request_hash"] != request_hash:
                        raise IdempotencyConflictError(
                            "Idempotency-Key was already used for another exception"
                        )
                    if int(reserved.get("response_status", 425)) == 425:
                        raise IdempotencyConflictError(
                            "An identical investigation is already in progress"
                        )
                    return InvestigationResponse.model_validate(reserved["response_body"])
            self._repository.record_audit_event(
                organization_id, "INVESTIGATION_STARTED", exception.id
            )
            response = self._investigate(organization_id, exception)
            self._repository.record_audit_event(
                organization_id, "INVESTIGATION_RESULT_VALIDATED", response.investigation_id
            )
            if response.recommended_action_code is not None:
                self._repository.record_audit_event(
                    organization_id, "RECOMMENDATION_CREATED", response.investigation_id
                )
            self._idempotency[key] = (exception_id, response)
            self._results[response.investigation_id] = (organization_id, response)
            if self._durable:
                body = response.model_dump(mode="json")
                try:
                    self._repository.save_investigation(organization_id, body)
                except Exception:
                    self._repository.release_idempotency(organization_id, idempotency_key)
                    raise
                self._repository.complete_idempotency(
                    organization_id,
                    idempotency_key,
                    200 if response.status != InvestigationStatus.FAILED else 503,
                    body,
                )
            return response

    def get(self, organization_id: str, investigation_id: str) -> InvestigationResponse:
        if self._durable:
            response = self._repository.get_investigation(organization_id, investigation_id)
            if response is not None:
                return InvestigationResponse.model_validate(response)
        result = self._results.get(investigation_id)
        if result is None or result[0] != organization_id:
            raise InvestigationNotFoundError(investigation_id)
        return result[1]

    def get_tool_calls(self, organization_id: str, investigation_id: str) -> list[ToolCall]:
        if self._durable:
            response = self._repository.get_investigation(organization_id, investigation_id)
            if response is None:
                raise InvestigationNotFoundError(investigation_id)
            return [
                ToolCall.model_validate(call)
                for call in self._repository.get_investigation_tool_calls(
                    organization_id, investigation_id
                )
            ]
        return self.get(organization_id, investigation_id).tool_calls

    @property
    def _durable(self) -> bool:
        return getattr(self._repository, "supports_workflow_persistence", False) is True

    @staticmethod
    def _request_hash(exception_id: str) -> str:
        return sha256(
            json.dumps({"exception_id": exception_id}, sort_keys=True).encode()
        ).hexdigest()

    def investigate_lifecycle(
        self, organization_id: str, exception: ExceptionSummary, lifecycle: Any
    ) -> InvestigationResponse:
        return self._investigate(organization_id, exception, lifecycle)

    def _investigate(
        self, organization_id: str, exception: ExceptionSummary, lifecycle: Any | None = None
    ) -> InvestigationResponse:
        started_at = datetime.now(UTC)
        try:
            if lifecycle is None:
                lifecycle = self._repository.lifecycle(organization_id, exception.order_id)
        except LifecycleNotFoundError as error:
            raise InvestigationNotFoundError(exception.id) from error

        tool_calls: list[ToolCall] = []
        evidence: list[EvidenceItem] = []
        available_tools = self._investigation_tools(exception.type)
        findings = [
            {
                "code": code,
                "message": f"Deterministic finding: {code}",
                "exposure_minor": int(exception.financial_exposure * 100),
            }
            for code in exception.rules_triggered
        ]
        candidate: InvestigationCandidate | None = None
        next_step = getattr(self._provider, "next_step", None)
        if callable(next_step):
            for _ in range(8):
                trace = [
                    {
                        "sequence_no": call.sequence_no,
                        "name": call.name,
                        "arguments": call.arguments,
                        "status": call.status,
                        "result_summary": call.result_summary,
                    }
                    for call in tool_calls
                ]
                try:
                    decision = next_step(
                        exception,
                        findings,
                        evidence,
                        trace,
                        # Once every relevant evidence source has been inspected,
                        # require a structured final answer instead of allowing the
                        # provider to keep selecting an already-used tool.
                        [] if len(tool_calls) >= len(available_tools) else available_tools,
                    )
                except ProviderUnavailable as error:
                    return _with_metadata(
                        self._failed_response(exception, tool_calls, error),
                        started_at,
                        self._provider,
                    )
                except (TypeError, ValueError) as error:
                    return _with_metadata(
                        self._unresolved_response(exception, tool_calls, evidence, str(error)),
                        started_at,
                        self._provider,
                    )
                if decision.action == "final":
                    try:
                        candidate = InvestigationCandidate.model_validate(
                            _normalize_provider_candidate(decision.candidate or {})
                        )
                    except ValidationError as error:
                        _logger.warning(
                            "investigation_candidate_invalid provider=%s model=%s errors=%s",
                            getattr(self._provider, "provider", "unknown"),
                            getattr(self._provider, "model", "unknown"),
                            str(error).replace("\n", " ")[:500],
                        )
                        candidate = InvestigationCandidate(
                            status=InvestigationStatus.UNRESOLVED,
                            root_cause_code=None,
                            summary="Provider output failed strict validation.",
                            missing_evidence=["A valid structured provider result was not returned."],
                            recommended_action_code=None,
                            requires_human_review=True,
                        )
                    break
                if decision.action != "tool" or decision.tool_name not in available_tools:
                    return _with_metadata(
                        self._unresolved_response(
                            exception, tool_calls, evidence, "Provider requested a non-allowlisted tool."
                        ),
                        started_at,
                        self._provider,
                    )
                arguments = decision.arguments or {}
                if any(
                    call.name == decision.tool_name and call.arguments == arguments
                    for call in tool_calls
                ):
                    return _with_metadata(
                        self._unresolved_response(
                            exception, tool_calls, evidence, "Provider repeated the same evidence request."
                        ),
                        started_at,
                        self._provider,
                    )
                try:
                    result = self._tools.invoke(
                        decision.tool_name,
                        organization_id,
                        lifecycle,
                        exception.id,
                        arguments,
                    )
                except ValueError as error:
                    tool_calls.append(
                        ToolCall(
                            name=decision.tool_name,
                            target=exception.order_id,
                            status="SKIPPED",
                            duration_ms=0,
                            sequence_no=len(tool_calls) + 1,
                            arguments=arguments,
                            result_summary=str(error),
                        )
                    )
                    return _with_metadata(
                        self._unresolved_response(exception, tool_calls, evidence, str(error)),
                        started_at,
                        self._provider,
                    )
                call = result.call.model_copy(update={"sequence_no": len(tool_calls) + 1})
                call = call.model_copy(
                    update={
                        "provider": getattr(self._provider, "provider", "unknown"),
                        "model": getattr(self._provider, "model", "unknown"),
                    }
                )
                tool_calls.append(call)
                self._repository.record_audit_event(
                    organization_id, "INVESTIGATION_TOOL_CALLED", call.name
                )
                evidence.extend(call.evidence)
            if candidate is None:
                return _with_metadata(
                    self._unresolved_response(
                        exception, tool_calls, evidence, "The bounded tool-call limit was reached."
                    ),
                    started_at,
                    self._provider,
                )
        else:
            # Compatibility path for legacy test doubles; configured production providers
            # implement next_step and always use the iterative loop above.
            try:
                selector = getattr(self._provider, "select_tools", None)
                selected_tools = (
                    selector(exception, available_tools)
                    if callable(selector)
                    else self._fallback_tools(exception)
                )
                names = [name for name in selected_tools if name in available_tools][:8]
                for name in names:
                    result = self._tools.invoke(name, organization_id, lifecycle, exception.id)
                    tool_calls.append(
                        result.call.model_copy(
                            update={
                                "sequence_no": len(tool_calls) + 1,
                                "provider": getattr(self._provider, "provider", "unknown"),
                                "model": getattr(self._provider, "model", "unknown"),
                            }
                        )
                    )
                    evidence.extend(result.call.evidence)
                for attempt in range(2):
                    try:
                        candidate = InvestigationCandidate.model_validate(
                            self._provider.investigate(exception, evidence)
                        )
                        break
                    except ValidationError:
                        if attempt == 1:
                            raise
            except ProviderUnavailable as error:
                return _with_metadata(
                    self._failed_response(exception, tool_calls, error),
                    started_at,
                    self._provider,
                )
            except (ValidationError, TypeError, ValueError):
                candidate = InvestigationCandidate(
                    status=InvestigationStatus.UNRESOLVED,
                    root_cause_code=None,
                    summary="Provider output failed strict validation.",
                    missing_evidence=["A valid structured provider result was not returned."],
                    recommended_action_code=None,
                    requires_human_review=True,
                )

        assert candidate is not None
        verification = verify_candidate(candidate, exception.type, lifecycle)
        return _with_metadata(InvestigationResponse(
            **verification.candidate.model_dump(),
            investigation_id=f"INV-{uuid4().hex[:12].upper()}",
            exception_id=exception.id,
            evidence_score=verification.evidence_score,
            tool_calls=tool_calls,
            created_at=datetime.now(UTC),
            verifier_passed=not verification.issues,
            verifier_issues=verification.issues,
            rejected_evidence=verification.rejected_evidence,
        ), started_at, self._provider)

    @staticmethod
    def _investigation_tools(exception_type: ExceptionType) -> list[str]:
        """Expose only the evidence sources that can resolve this deterministic finding."""
        plans: dict[ExceptionType, list[str]] = {
            ExceptionType.REFUND_WITHOUT_INVENTORY_RETURN: [
                "get_order", "get_payments_for_order", "get_refunds_for_order",
                "get_invoice_for_order", "get_inventory_movements", "get_employee_action_logs",
            ],
            ExceptionType.REFUND_WITHOUT_ERP_REVERSAL: [
                "get_order", "get_refunds_for_order", "get_invoice_for_order"
            ],
            ExceptionType.ERP_INVOICE_MISSING: [
                "get_order", "get_payments_for_order", "get_invoice_for_order"
            ],
            ExceptionType.ERP_AMOUNT_MISMATCH: [
                "get_order", "get_invoice_for_order"
            ],
            ExceptionType.MISSING_SETTLEMENT: [
                "get_order", "get_payment", "get_settlements_for_order"
            ],
            ExceptionType.DUPLICATE_PAYMENT: [
                "get_order", "get_payments_for_order", "get_settlements_for_order"
            ],
            ExceptionType.AMBIGUOUS_ASSOCIATION: [
                "get_order", "get_payments_for_order", "get_invoice_for_order",
                "get_settlements_for_order", "get_refunds_for_order", "get_related_exceptions"
            ],
        }
        return plans.get(exception_type, [
            "get_order", "get_payments_for_order", "get_invoice_for_order",
            "get_inventory_movements", "get_employee_action_logs",
        ])

    @staticmethod
    def _fallback_tools(exception: ExceptionSummary) -> list[str]:
        common = ["get_order", "get_payments_for_order"]
        if exception.type.value in {"DUPLICATE_PAYMENT", "AMBIGUOUS_ASSOCIATION"}:
            return [
                *common,
                "get_invoice_for_order",
                "get_settlements_for_order",
                "get_refunds_for_order",
            ]
        return [
            *common,
            "get_invoice_for_order",
            "get_inventory_movements",
            "get_employee_action_logs",
        ]

    @staticmethod
    def _unresolved_response(
        exception: ExceptionSummary,
        tool_calls: list[ToolCall],
        evidence: list[EvidenceItem],
        reason: str,
    ) -> InvestigationResponse:
        return InvestigationResponse(
            status=InvestigationStatus.UNRESOLVED,
            root_cause_code=RootCauseCode.AMBIGUOUS_ASSOCIATION
            if exception.type.value in {"DUPLICATE_PAYMENT", "AMBIGUOUS_ASSOCIATION"}
            else None,
            summary="The deterministic evidence relationship is ambiguous; no root-cause conclusion was forced.",
            supporting_evidence=evidence[:30],
            contradictory_evidence=[],
            missing_evidence=[reason],
            recommended_action_code=RecommendationCode.REQUEST_MANUAL_REVIEW,
            requires_human_review=True,
            investigation_id=f"INV-{uuid4().hex[:12].upper()}",
            exception_id=exception.id,
            evidence_score=0,
            tool_calls=tool_calls,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _failed_response(
        exception: ExceptionSummary, tool_calls: list[ToolCall], error: ProviderUnavailable
    ) -> InvestigationResponse:
        return InvestigationResponse(
            status=InvestigationStatus.FAILED,
            root_cause_code=None,
            summary="AI provider unavailable; deterministic evidence remains available for manual review.",
            supporting_evidence=[],
            contradictory_evidence=[],
            missing_evidence=[str(error)],
            recommended_action_code=None,
            requires_human_review=True,
            investigation_id=f"INV-{uuid4().hex[:12].upper()}",
            exception_id=exception.id,
            evidence_score=0,
            tool_calls=tool_calls,
            created_at=datetime.now(UTC),
            provider_error_category=error.info.category,
            provider_retryable=error.info.retryable,
            failure_stage=error.info.stage,
            failure_iteration=error.info.iteration,
            failure_detail=str(error)[:500],
        )


def _with_metadata(
    response: InvestigationResponse, started_at: datetime, provider: Any
) -> InvestigationResponse:
    completed_at = datetime.now(UTC)
    return response.model_copy(
        update={
            "provider": getattr(provider, "provider", "unknown"),
            "model": getattr(provider, "model", "unknown"),
            "originally_requested_provider": getattr(
                provider, "originally_requested_provider", getattr(provider, "provider", "unknown")
            ),
            "actual_provider_used": getattr(provider, "provider", "unknown"),
            "model_used": getattr(provider, "model", "unknown"),
            "fallback_used": bool(getattr(provider, "fallback_used", False)),
            "fallback_reason": getattr(provider, "fallback_reason", None),
            "prompt_version": getattr(provider, "prompt_version", "p0-iterative-v1"),
            "started_at": started_at,
            "completed_at": completed_at,
            "latency_ms": max(0, int((completed_at - started_at).total_seconds() * 1000)),
        }
    )


def _normalize_provider_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Normalize documented provider aliases while retaining strict candidate validation."""
    allowed = {
        "status", "root_cause_code", "summary", "supporting_evidence",
        "contradictory_evidence", "missing_evidence", "recommended_action_code",
        "requires_human_review",
    }
    result = {key: value for key, value in candidate.items() if key in allowed}
    root_aliases = {
        "REFUND_WITHOUT_INVENTORY_RETURN": "INVENTORY_REVERSAL_MISSING",
        "REFUND_WITHOUT_ERP_REVERSAL": "ERP_REVERSAL_MISSING",
        "MISSING_SETTLEMENT": "SETTLEMENT_MISSING",
    }
    root = result.get("root_cause_code")
    if root in root_aliases:
        result["root_cause_code"] = root_aliases[root]
    action_aliases = {
        "INITIATE_INVENTORY_INSPECTION": "REQUEST_INVENTORY_VERIFICATION",
        "REQUEST_INVENTORY_INSPECTION": "REQUEST_INVENTORY_VERIFICATION",
        "FLAG_FOR_INVENTORY_AUDIT": "REQUEST_INVENTORY_VERIFICATION",
        "REVIEW_ERP_REVERSAL": "REQUEST_ERP_REVERSAL_REVIEW",
        "REQUEST_ERP_REVIEW": "REQUEST_ERP_REVERSAL_REVIEW",
        "REVIEW_PAYMENT": "REQUEST_PAYMENT_REVIEW",
        "REQUEST_REVIEW": "REQUEST_MANUAL_REVIEW",
    }
    action = result.get("recommended_action_code")
    if action in action_aliases:
        result["recommended_action_code"] = action_aliases[action]
    elif action is not None and action not in {
        "REQUEST_INVENTORY_VERIFICATION", "REQUEST_ERP_REVERSAL_REVIEW",
        "REQUEST_PAYMENT_REVIEW", "REQUEST_MANUAL_REVIEW",
    }:
        # An unrecognized action is never allowed to cross the API boundary.
        result["recommended_action_code"] = None
    for field in ("supporting_evidence", "contradictory_evidence"):
        result[field] = [_normalize_provider_evidence(item) for item in result.get(field, []) if isinstance(item, dict)]
    return result


def _normalize_provider_evidence(item: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "source", "record_id", "fact", "field", "operator", "expected_value",
    }
    result = {key: value for key, value in item.items() if key in allowed}
    result["source"] = {
        "inventory_movements": "inventory",
        "employee_actions": "employee_action",
    }.get(str(result.get("source")), result.get("source"))
    if result.get("record_id") is None and result.get("operator") is None:
        # Missing-record claims must be explicit before deterministic verification.
        result["operator"] = "missing"
    return result
