from dataclasses import asdict
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from app.evaluation.metrics import evaluate_dataset
from app.evaluation.schemas import (
    EvaluationReportResponse,
    EvaluationResponse,
    EvaluationRunRequest,
)
from app.simulator.generator import GeneratorConfig, generate_dataset


class EvaluationConflictError(ValueError):
    pass


class EvaluationNotFoundError(LookupError):
    pass


class EvaluationService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._latest: dict[str, EvaluationResponse] = {}
        self._idempotency: dict[tuple[str, str], tuple[EvaluationRunRequest, EvaluationResponse]] = {}

    def run(self, organization_id: str, request: EvaluationRunRequest, idempotency_key: str) -> EvaluationResponse:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("Idempotency-Key must be between 1 and 128 characters")
        key = (organization_id, idempotency_key)
        with self._lock:
            previous = self._idempotency.get(key)
            if previous is not None:
                previous_request, response = previous
                if previous_request != request:
                    raise EvaluationConflictError("Idempotency-Key was already used for another evaluation")
                return response
            dataset = generate_dataset(GeneratorConfig(request.orders, request.seed, request.anomaly_rate, organization_id))
            report, _ = evaluate_dataset(dataset)
            response = EvaluationResponse(
                evaluation_id=f"EVAL-{uuid4().hex[:12].upper()}",
                organization_id=organization_id,
                seed=request.seed,
                anomaly_rate=request.anomaly_rate,
                report=EvaluationReportResponse.model_validate(asdict(report)),
                created_at=datetime.now(UTC),
            )
            self._latest[organization_id] = response
            self._idempotency[key] = (request, response)
            return response

    def latest(self, organization_id: str) -> EvaluationResponse:
        response = self._latest.get(organization_id)
        if response is None:
            raise EvaluationNotFoundError(organization_id)
        return response
