import hashlib
import json
from datetime import UTC, datetime
from typing import Any
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

    def lifecycle(self, organization_id: str, investigation_id: str, run_id: str, result_id: str):
        """Read immutable uploaded evidence, never the seeded demo lifecycle."""
        result = self._repository.get_reconciliation_result(organization_id, investigation_id, run_id, result_id)
        run = self._repository.latest_reconciliation_run(organization_id, investigation_id)
        if result is None or run is None or run["id"] != run_id:
            raise ReconciliationNotFound(result_id)
        versions = self._repository.list_dataset_versions(organization_id, investigation_id)
        version = next((v for v in versions if v["id"] == run["dataset_version_id"]), None)
        if version is None:
            raise ReconciliationNotFound(result_id)
        records = self._repository.list_normalized_records(organization_id, investigation_id, str(version["id"]), max(1, int(version["record_count"])))
        lifecycle = next((item for item in construct_lifecycles(organization_id, records) if item.order["order_id"] == result["order_id"]), None)
        if lifecycle is None:
            raise ReconciliationNotFound(result_id)
        return lifecycle

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
            context.organization_id,
            investigation_id,
            str(version["id"]),
            max(int(version.get("record_count", 0)), 1),
        )
        expected_records = int(version.get("record_count", 0))
        loaded_records = len(records)
        if loaded_records != expected_records:
            return self._persist_incomplete(
                context,
                investigation_id,
                version,
                idempotency_key,
                request_hash,
                expected_records,
                loaded_records,
                0,
                max(expected_records - loaded_records, 0),
                f"Expected {expected_records} normalized records but loaded {loaded_records}.",
            )
        try:
            lifecycles = construct_lifecycles(context.organization_id, records)
        except LifecycleConstructionError as error:
            return self._persist_incomplete(
                context,
                investigation_id,
                version,
                idempotency_key,
                request_hash,
                expected_records,
                loaded_records,
                0,
                loaded_records,
                str(error),
            )
        if not lifecycles:
            return self._persist_incomplete(
                context,
                investigation_id,
                version,
                idempotency_key,
                request_hash,
                expected_records,
                loaded_records,
                0,
                loaded_records,
                "The normalized dataset contains no constructible order lifecycles.",
            )
        consumed_records = _consumed_record_count(lifecycles)
        if consumed_records != loaded_records:
            return self._persist_incomplete(
                context,
                investigation_id,
                version,
                idempotency_key,
                request_hash,
                expected_records,
                loaded_records,
                consumed_records,
                loaded_records - consumed_records,
                "One or more normalized records were not consumed by a lifecycle.",
            )
        results = [reconcile_lifecycle(lifecycle) for lifecycle in lifecycles]
        started_at = datetime.now(UTC)
        run = {
            "id": f"RR-{uuid4().hex[:12].upper()}",
            "organization_id": context.organization_id,
            "financial_investigation_id": investigation_id,
            "dataset_version_id": str(version["id"]),
            "status": "COMPLETED",
            "records_expected": expected_records,
            "records_loaded": loaded_records,
            "records_consumed": consumed_records,
            "orphan_record_count": 0,
            "rejected_record_count": 0,
            "failure_reason": None,
            "lifecycle_count": len(results),
            "reconciled_count": sum(item.status.startswith("RECONCILED") for item in results),
            "exception_count": sum(item.status == "EXCEPTION" for item in results),
            "ambiguous_count": sum(item.status == "AMBIGUOUS" for item in results),
            "open_exposure_minor": sum(
                item.exposure_minor
                for item in results
                if item.status in {"EXCEPTION", "AMBIGUOUS"}
                and item.exposure_category in {"POTENTIAL_EXPOSURE", "CONTROL_RISK"}
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
                        "exposure_category": finding.exposure_category,
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

    def _persist_incomplete(
        self,
        context: ActorContext,
        investigation_id: str,
        version: dict[str, object],
        idempotency_key: str,
        request_hash: str,
        expected_records: int,
        loaded_records: int,
        consumed_records: int,
        orphan_record_count: int,
        reason: str,
    ) -> ReconciliationRunResponse:
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
        now = datetime.now(UTC)
        run = {
            "id": f"RR-{uuid4().hex[:12].upper()}",
            "organization_id": context.organization_id,
            "financial_investigation_id": investigation_id,
            "dataset_version_id": str(version["id"]),
            "status": "INCOMPLETE",
            "records_expected": expected_records,
            "records_loaded": loaded_records,
            "records_consumed": consumed_records,
            "orphan_record_count": max(orphan_record_count, 0),
            "rejected_record_count": 0,
            "failure_reason": reason[:500],
            "lifecycle_count": 0,
            "reconciled_count": 0,
            "exception_count": 0,
            "ambiguous_count": 0,
            "open_exposure_minor": 0,
            "started_at": now,
            "completed_at": datetime.now(UTC),
        }
        try:
            saved = self._repository.save_reconciliation_run(
                context.organization_id, run, []
            )
        except Exception:
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise
        response = ReconciliationRunResponse.model_validate(saved)
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 200, response.model_dump(mode="json")
        )
        self._repository.record_audit_event(
            context.organization_id,
            "RECONCILIATION_RUN_INCOMPLETE",
            str(saved["id"]),
            context.actor_id,
        )
        self._repository.update_financial_investigation_status(
            context.organization_id, investigation_id, "FAILED"
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


def _consumed_record_count(lifecycles: list[Any]) -> int:
    consumed: set[str] = set()
    for lifecycle in lifecycles:
        rows = (
            lifecycle.order,
            *lifecycle.payments,
            *lifecycle.settlements,
            *lifecycle.invoices,
            *lifecycle.refunds,
            *lifecycle.inventory_movements,
            *lifecycle.employee_actions,
        )
        consumed.update(
            str(row["__normalized_record_id"])
            for row in rows
            if row.get("__normalized_record_id")
        )
    return len(consumed)
