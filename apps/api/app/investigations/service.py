import json
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.domain.lifecycle import LifecycleNotFoundError
from app.domain.schemas import ExceptionSummary
from app.investigations.provider import AIClient, ProviderUnavailable
from app.investigations.schemas import (
    InvestigationCandidate,
    InvestigationResponse,
    InvestigationStatus,
    ToolCall,
)
from app.investigations.tools import EvidenceToolRegistry
from app.investigations.verifier import verify_candidate
from app.repositories.contracts import LifecycleRepository


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

    def start(self, organization_id: str, exception_id: str, idempotency_key: str) -> InvestigationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (organization_id, idempotency_key)
        with self._lock:
            if self._durable:
                previous = self._repository.get_idempotency(organization_id, idempotency_key)
                request_hash = self._request_hash(exception_id)
                if previous is not None:
                    if previous["request_hash"] != request_hash:
                        raise IdempotencyConflictError("Idempotency-Key was already used for another exception")
                    return InvestigationResponse.model_validate(previous["response_body"])
            previous = self._idempotency.get(key)
            if previous is not None:
                previous_exception_id, response = previous
                if previous_exception_id != exception_id:
                    raise IdempotencyConflictError("Idempotency-Key was already used for another exception")
                return response

            exception = self._repository.get_exception(organization_id, exception_id)
            if exception is None:
                raise InvestigationNotFoundError(exception_id)
            self._repository.record_audit_event(organization_id, "INVESTIGATION_STARTED", exception.id)
            response = self._investigate(organization_id, exception)
            self._repository.record_audit_event(organization_id, "INVESTIGATION_RESULT_VALIDATED", response.investigation_id)
            self._idempotency[key] = (exception_id, response)
            self._results[response.investigation_id] = (organization_id, response)
            if self._durable:
                body = response.model_dump(mode="json")
                self._repository.save_investigation(organization_id, body)
                self._repository.put_idempotency(organization_id, "system", idempotency_key, self._request_hash(exception_id), 200 if response.status != InvestigationStatus.FAILED else 503, body)
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
            return [ToolCall.model_validate(call) for call in self._repository.get_investigation_tool_calls(organization_id, investigation_id)]
        return self.get(organization_id, investigation_id).tool_calls

    @property
    def _durable(self) -> bool:
        return getattr(self._repository, "supports_workflow_persistence", False) is True

    @staticmethod
    def _request_hash(exception_id: str) -> str:
        return sha256(json.dumps({"exception_id": exception_id}, sort_keys=True).encode()).hexdigest()

    def _investigate(self, organization_id: str, exception: ExceptionSummary) -> InvestigationResponse:
        try:
            lifecycle = self._repository.lifecycle(organization_id, exception.order_id)
        except LifecycleNotFoundError as error:
            raise InvestigationNotFoundError(exception.id) from error

        tool_calls: list[ToolCall] = []
        evidence = []
        for name in (
            "get_order",
            "get_payments_for_order",
            "get_refunds_for_payment",
            "get_invoice_for_order",
            "get_inventory_movements",
            "get_employee_action_logs",
        ):
            try:
                result = self._tools.invoke(name, organization_id, lifecycle, exception.id)
            except ValueError as error:
                return self._failed_response(exception, tool_calls, str(error))
            tool_calls.append(result.call)
            self._repository.record_audit_event(organization_id, "INVESTIGATION_TOOL_CALLED", result.call.name)
            evidence.extend(result.call.evidence)

        candidate = None
        for attempt in range(2):
            try:
                raw_candidate = self._provider.investigate(exception, evidence)
                candidate = InvestigationCandidate.model_validate(raw_candidate)
                break
            except ProviderUnavailable as error:
                return self._failed_response(exception, tool_calls, str(error))
            except ValidationError:
                if attempt == 1:
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
        return InvestigationResponse(
            **verification.candidate.model_dump(),
            investigation_id=f"INV-{uuid4().hex[:12].upper()}",
            exception_id=exception.id,
            evidence_score=verification.evidence_score,
            tool_calls=tool_calls,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _failed_response(exception: ExceptionSummary, tool_calls: list[ToolCall], reason: str) -> InvestigationResponse:
        return InvestigationResponse(
            status=InvestigationStatus.FAILED,
            root_cause_code=None,
            summary="Investigation provider is unavailable; deterministic evidence remains available for manual review.",
            supporting_evidence=[],
            contradictory_evidence=[],
            missing_evidence=[reason],
            recommended_action_code=None,
            requires_human_review=True,
            investigation_id=f"INV-{uuid4().hex[:12].upper()}",
            exception_id=exception.id,
            evidence_score=0,
            tool_calls=tool_calls,
            created_at=datetime.now(UTC),
        )
