import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.controls.schemas import ActorContext
from app.lifecycle_construction.service import LifecycleConstructionError, construct_lifecycles
from app.reconciliation.engine import reconcile_lifecycle
from app.reconciliation.schemas import ReconciliationResultResponse, ReconciliationRunResponse
from app.repositories.contracts import WorkflowRepository


class ReconciliationNotFound(LookupError):
    pass


class ReconciliationBlocked(ValueError):
    pass


class ReconciliationConflict(ValueError):
    pass


class ReconciliationService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def run(
        self,
        context: ActorContext,
        investigation_id: str,
        dataset_version_id: str | None,
        idempotency_key: str,
    ) -> ReconciliationRunResponse:
        request_hash = hashlib.sha256(
            json.dumps(
                {"investigation_id": investigation_id, "dataset_version_id": dataset_version_id},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        replay = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if replay is not None:
            if replay.get("request_hash") != request_hash:
                raise ReconciliationConflict("Idempotency-Key was already used for another request")
            if int(replay.get("response_status", 425)) == 425:
                raise ReconciliationConflict(
                    "An identical reconciliation request is already in progress"
                )
            return ReconciliationRunResponse.model_validate(replay["response_body"])
        version = (
            self._repository.latest_dataset_version(context.organization_id, investigation_id)
            if dataset_version_id is None
            else next(
                (
                    item
                    for item in self._repository.list_dataset_versions(
                        context.organization_id, investigation_id
                    )
                    if item["id"] == dataset_version_id
                ),
                None,
            )
        )
        if version is None:
            raise ReconciliationNotFound("No normalized dataset exists for this investigation")
        records = self._repository.list_normalized_records(
            context.organization_id, investigation_id, str(version["id"])
        )
        try:
            lifecycles = construct_lifecycles(context.organization_id, records)
        except LifecycleConstructionError as error:
            raise ReconciliationBlocked(str(error)) from error
        if not lifecycles:
            raise ReconciliationBlocked(
                "The normalized dataset contains no constructible order lifecycles"
            )
        results = [reconcile_lifecycle(lifecycle) for lifecycle in lifecycles]
        started_at = datetime.now(UTC)
        run = {
            "id": f"RR-{uuid4().hex[:12].upper()}",
            "organization_id": context.organization_id,
            "financial_investigation_id": investigation_id,
            "dataset_version_id": str(version["id"]),
            "status": "COMPLETED",
            "lifecycle_count": len(results),
            "reconciled_count": sum(item.status.startswith("RECONCILED") for item in results),
            "exception_count": sum(item.status == "EXCEPTION" for item in results),
            "ambiguous_count": sum(item.status == "AMBIGUOUS" for item in results),
            "open_exposure_minor": sum(
                item.exposure_minor for item in results if item.status in {"EXCEPTION", "AMBIGUOUS"}
            ),
            "started_at": started_at,
            "completed_at": datetime.now(UTC),
        }
        result_rows = [
            {
                "id": f"RRES-{uuid4().hex[:12].upper()}",
                "run_id": run["id"],
                "order_id": result.order_id,
                "status": result.status,
                "exception_type": result.exception_type,
                "severity": result.severity,
                "exposure_minor": result.exposure_minor,
                "findings": [
                    {
                        "code": finding.code,
                        "message": finding.message,
                        "exposure_minor": finding.exposure_minor,
                    }
                    for finding in result.findings
                ],
            }
            for result in results
        ]
        existing = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if existing is not None:
            if existing.get("request_hash") != request_hash:
                raise ReconciliationConflict("Idempotency-Key was already used for another request")
            if int(existing.get("response_status", 425)) == 425:
                raise ReconciliationConflict(
                    "An identical reconciliation request is already in progress"
                )
            return ReconciliationRunResponse.model_validate(existing["response_body"])
        try:
            saved = self._repository.save_reconciliation_run(
                context.organization_id, run, result_rows
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        response = ReconciliationRunResponse.model_validate(saved)
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
        )
        for result in result_rows:
            if result["status"] in {"EXCEPTION", "AMBIGUOUS"}:
                self._repository.record_audit_event(
                    context.organization_id,
                    "EXCEPTION_CREATED",
                    str(result["id"]),
                    context.actor_id,
                    str(run["id"]),
                )
        self._repository.record_audit_event(
            context.organization_id,
            "RECONCILIATION_RUN_COMPLETED",
            str(saved["id"]),
            context.actor_id,
        )
        self._repository.update_financial_investigation_status(
            context.organization_id, investigation_id, "RECONCILED"
        )
        return response

    def latest(self, organization_id: str, investigation_id: str) -> ReconciliationRunResponse:
        result = self._repository.latest_reconciliation_run(organization_id, investigation_id)
        if result is None:
            raise ReconciliationNotFound(investigation_id)
        return ReconciliationRunResponse.model_validate(result)

    def results(
        self, organization_id: str, investigation_id: str, run_id: str, limit: int = 1000
    ) -> list[ReconciliationResultResponse]:
        return [
            ReconciliationResultResponse.model_validate(item)
            for item in self._repository.list_reconciliation_results(
                organization_id, investigation_id, run_id, limit
            )
        ]
