import json
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from app.controls.schemas import ActorContext
from app.domain.schemas import ExceptionStatus, ExceptionSummary, ExceptionType, Severity
from app.investigations.provider import AIClient
from app.investigations.schemas import InvestigationResponse
from app.investigations.service import InvestigationService
from app.lifecycle_construction.service import LifecycleConstructionError, construct_lifecycles
from app.repositories.contracts import WorkflowRepository


class FinancialExceptionNotFound(LookupError):
    pass


class FinancialExceptionConflict(ValueError):
    pass


class FinancialExceptionInvestigationService:
    def __init__(self, repository: WorkflowRepository, provider: AIClient) -> None:
        self._repository = repository
        self._investigator = InvestigationService(repository, provider)

    def investigate(
        self,
        context: ActorContext,
        investigation_id: str,
        run_id: str,
        result_id: str,
        idempotency_key: str,
    ) -> InvestigationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        request_hash = sha256(
            json.dumps(
                {"investigation_id": investigation_id, "run_id": run_id, "result_id": result_id},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        previous = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if previous is not None:
            if previous.get("request_hash") != request_hash:
                raise FinancialExceptionConflict(
                    "Idempotency-Key was already used for another exception"
                )
            if int(previous.get("response_status", 425)) == 425:
                raise FinancialExceptionConflict(
                    "An identical exception investigation is already in progress"
                )
            return InvestigationResponse.model_validate(previous["response_body"])
        existing = self._repository.get_financial_exception_investigation(
            context.organization_id, investigation_id, result_id
        )
        if existing is not None:
            response = InvestigationResponse.model_validate(existing)
            self._repository.put_idempotency(
                context.organization_id,
                context.actor_id,
                idempotency_key,
                request_hash,
                200,
                response.model_dump(mode="json"),
            )
            return response
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
            or run.get("id") != run_id
            or financial_investigation is None
        ):
            raise FinancialExceptionNotFound(result_id)
        dataset_version = next(
            (
                item
                for item in self._repository.list_dataset_versions(
                    context.organization_id, investigation_id
                )
                if item.get("id") == run["dataset_version_id"]
            ),
            None,
        )
        records = self._repository.list_normalized_records(
            context.organization_id,
            investigation_id,
            str(run["dataset_version_id"]),
            max(int(dataset_version.get("record_count", 0)), 1) if dataset_version else 1000,
        )
        try:
            lifecycle = next(
                item
                for item in construct_lifecycles(context.organization_id, records)
                if item.order.get("order_id") == result["order_id"]
            )
        except (LifecycleConstructionError, StopIteration) as error:
            raise FinancialExceptionNotFound(result_id) from error
        exception_type = _exception_type(result.get("exception_type"))
        exception = ExceptionSummary(
            id=str(result_id),
            organization_id=context.organization_id,
            order_id=str(result["order_id"]),
            type=exception_type,
            severity=Severity(str(result.get("severity", "MEDIUM"))),
            status=ExceptionStatus.OPEN,
            financial_exposure=Decimal(int(result.get("exposure_minor", 0))) / Decimal(100),
            currency=str(financial_investigation["base_currency"]),
            detected_at=datetime.now(UTC),
            rules_triggered=[str(item.get("code")) for item in result.get("findings", [])],
        )
        response = self._investigator.investigate_lifecycle(
            context.organization_id, exception, lifecycle
        )
        body = response.model_dump(mode="json")
        existing = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if existing is not None:
            if existing.get("request_hash") != request_hash:
                raise FinancialExceptionConflict(
                    "Idempotency-Key was already used for another exception"
                )
            if int(existing.get("response_status", 425)) == 425:
                raise FinancialExceptionConflict(
                    "An identical exception investigation is already in progress"
                )
            return InvestigationResponse.model_validate(existing["response_body"])
        try:
            self._repository.save_financial_exception_investigation(
                context.organization_id, investigation_id, result_id, body
            )
            self._repository.save_financial_exception_investigation_tool_calls(
                context.organization_id,
                response.investigation_id,
                [item.model_dump(mode="json") for item in response.tool_calls],
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        self._repository.complete_idempotency(context.organization_id, idempotency_key, 200, body)
        self._repository.record_audit_event(
            context.organization_id,
            "FINANCIAL_EXCEPTION_INVESTIGATION_COMPLETED",
            response.investigation_id,
            context.actor_id,
        )
        if response.recommended_action_code is not None:
            self._repository.record_audit_event(
                context.organization_id,
                "RECOMMENDATION_CREATED",
                response.investigation_id,
                context.actor_id,
            )
        return response

    def get(
        self, organization_id: str, investigation_id: str, run_id: str, result_id: str
    ) -> InvestigationResponse:
        """Return a persisted result only through its organization-scoped run and result."""
        result = self._repository.get_reconciliation_result(
            organization_id, investigation_id, run_id, result_id
        )
        if result is None:
            raise FinancialExceptionNotFound(result_id)
        response = self._repository.get_financial_exception_investigation(
            organization_id, investigation_id, result_id
        )
        if response is None:
            raise FinancialExceptionNotFound(result_id)
        return InvestigationResponse.model_validate(response)


def _exception_type(value: object) -> ExceptionType:
    try:
        return ExceptionType(str(value))
    except ValueError:
        return ExceptionType.AMBIGUOUS_ASSOCIATION
