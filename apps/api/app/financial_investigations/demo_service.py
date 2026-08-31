from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.controls.schemas import ActorContext
from app.financial_investigations.demo import build_source_files
from app.financial_investigations.files import inspect_upload, remove_upload, store_upload
from app.financial_investigations.schemas import (
    DemoDataRequest,
    DemoDataResponse,
    SourceFileResponse,
)
from app.financial_investigations.service import (
    FinancialInvestigationConflict,
    FinancialInvestigationService,
)
from app.repositories.contracts import WorkflowRepository
from app.simulator.generator import SCENARIOS


class DemoDataService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository
        self._investigations = FinancialInvestigationService(repository)

    def generate(
        self,
        context: ActorContext,
        investigation_id: str,
        payload: DemoDataRequest,
        idempotency_key: str,
    ) -> DemoDataResponse:
        self._investigations.get(context.organization_id, investigation_id)
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        scenarios = tuple(payload.scenario_types) if payload.scenario_types else SCENARIOS[1:]
        invalid = sorted(set(scenarios) - set(SCENARIOS[1:]))
        if invalid:
            raise ValueError("Unsupported demo scenario type(s): " + ", ".join(invalid))
        request_hash = sha256(
            json.dumps(
                {**payload.model_dump(mode="json"), "investigation_id": investigation_id},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        existing = self._repository.get_idempotency(context.organization_id, idempotency_key)
        if existing is not None:
            if existing.get("request_hash") != request_hash:
                raise FinancialInvestigationConflict(
                    "Idempotency-Key was already used for another request"
                )
            if int(existing.get("response_status", 425)) == 425:
                raise FinancialInvestigationConflict(
                    "An identical demo generation request is already in progress"
                )
            return DemoDataResponse.model_validate(existing["response_body"])
        if self._repository.list_source_files(context.organization_id, investigation_id):
            raise FinancialInvestigationConflict(
                "Remove the existing source files before generating a fresh synthetic set"
            )
        reserved = self._repository.reserve_idempotency(
            context.organization_id, context.actor_id, idempotency_key, request_hash
        )
        if reserved is not None:
            if reserved.get("request_hash") != request_hash:
                raise FinancialInvestigationConflict(
                    "Idempotency-Key was already used for another request"
                )
            if int(reserved.get("response_status", 425)) == 425:
                raise FinancialInvestigationConflict(
                    "An identical demo generation request is already in progress"
                )
            return DemoDataResponse.model_validate(reserved["response_body"])

        stored: list[str] = []
        sources: list[SourceFileResponse] = []
        try:
            for index, (filename, content) in enumerate(
                build_source_files(payload, context.organization_id, scenarios)
            ):
                inspection = inspect_upload(filename, "text/csv", content)
                storage_reference = store_upload(content, inspection)
                stored.append(storage_reference)
                source = self._investigations.add_source(
                    context,
                    investigation_id,
                    {
                        "id": f"SRC-{uuid4().hex[:12].upper()}",
                        "original_filename": filename,
                        "storage_reference": storage_reference,
                        "mime_type": inspection.mime_type,
                        "size_bytes": inspection.size_bytes,
                        "row_count": inspection.row_count,
                        "column_count": inspection.column_count,
                        "status": "UPLOADED",
                        "created_at": datetime.now(UTC),
                        "sha256": inspection.sha256,
                    },
                    f"{idempotency_key}:source:{index}",
                )
                sources.append(source)
        except Exception:
            for storage_reference in stored:
                remove_upload(storage_reference)
            self._repository.release_idempotency(context.organization_id, idempotency_key)
            raise

        response = DemoDataResponse(
            financial_investigation_id=investigation_id,
            orders=payload.orders,
            seed=payload.seed,
            anomaly_rate=payload.anomaly_rate,
            scenario_types=list(scenarios),
            sources=sources,
        )
        self._repository.complete_idempotency(
            context.organization_id, idempotency_key, 201, response.model_dump(mode="json")
        )
        self._repository.record_audit_event(
            context.organization_id, "DEMO_DATA_GENERATED", investigation_id, context.actor_id
        )
        return response
