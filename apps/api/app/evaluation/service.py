import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any
from uuid import uuid4

from app.evaluation.metrics import evaluate_dataset
from app.evaluation.schemas import (
    EvaluationReportResponse,
    EvaluationResponse,
    EvaluationRunRequest,
)
from app.repositories.contracts import LifecycleRepository
from app.simulator.generator import GeneratorConfig, generate_dataset


class EvaluationConflictError(ValueError):
    pass


class EvaluationNotFoundError(LookupError):
    pass


class EvaluationService:
    def __init__(self, repository: LifecycleRepository | None = None) -> None:
        self._repository: Any = repository
        self._lock = RLock()
        self._latest: dict[str, EvaluationResponse] = {}
        self._idempotency: dict[
            tuple[str, str], tuple[EvaluationRunRequest, EvaluationResponse]
        ] = {}

    def run(
        self, organization_id: str, request: EvaluationRunRequest, idempotency_key: str
    ) -> EvaluationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (organization_id, idempotency_key)
        with self._lock:
            request_hash = self._request_hash(request)
            if self._durable and self._repository is not None:
                previous = self._repository.get_idempotency(organization_id, idempotency_key)
                if previous is not None:
                    if previous["request_hash"] != request_hash:
                        raise EvaluationConflictError(
                            "Idempotency-Key was already used for another evaluation"
                        )
                    if int(previous.get("response_status", 425)) == 425:
                        raise EvaluationConflictError(
                            "An identical evaluation is already in progress"
                        )
                    return EvaluationResponse.model_validate(previous["response_body"])
                reserved = self._repository.reserve_idempotency(
                    organization_id, "system", idempotency_key, request_hash
                )
                if reserved is not None:
                    if reserved["request_hash"] != request_hash:
                        raise EvaluationConflictError(
                            "Idempotency-Key was already used for another evaluation"
                        )
                    if int(reserved.get("response_status", 425)) == 425:
                        raise EvaluationConflictError(
                            "An identical evaluation is already in progress"
                        )
                    return EvaluationResponse.model_validate(reserved["response_body"])
            previous = self._idempotency.get(key)
            if previous is not None:
                previous_request, response = previous
                if previous_request != request:
                    raise EvaluationConflictError(
                        "Idempotency-Key was already used for another evaluation"
                    )
                return response
            try:
                dataset = generate_dataset(
                    GeneratorConfig(request.orders, request.seed, request.anomaly_rate, organization_id)
                )
                report, _ = evaluate_dataset(dataset)
                response = EvaluationResponse(
                    evaluation_id=f"EVAL-{uuid4().hex[:12].upper()}",
                    organization_id=organization_id,
                    seed=request.seed,
                    anomaly_rate=request.anomaly_rate,
                    report=EvaluationReportResponse.model_validate(asdict(report)),
                    created_at=datetime.now(UTC),
                )
            except Exception:
                if self._durable and self._repository is not None:
                    self._repository.release_idempotency(organization_id, idempotency_key)
                raise
            self._latest[organization_id] = response
            self._idempotency[key] = (request, response)
            if self._durable and self._repository is not None:
                body = response.model_dump(mode="json")
                try:
                    self._repository.save_evaluation(organization_id, body)
                except Exception:
                    self._repository.release_idempotency(organization_id, idempotency_key)
                    raise
                self._repository.complete_idempotency(organization_id, idempotency_key, 200, body)
            return response

    def latest(self, organization_id: str) -> EvaluationResponse:
        if self._durable and self._repository is not None:
            response = self._repository.get_latest_evaluation(organization_id)
            if response is not None:
                return EvaluationResponse.model_validate(response)
        response = self._latest.get(organization_id)
        if response is None:
            raise EvaluationNotFoundError(organization_id)
        return response

    @property
    def _durable(self) -> bool:
        return bool(
            self._repository is not None
            and getattr(self._repository, "supports_workflow_persistence", False) is True
        )

    @staticmethod
    def _request_hash(request: EvaluationRunRequest) -> str:
        payload = request.model_dump(mode="json")
        return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
