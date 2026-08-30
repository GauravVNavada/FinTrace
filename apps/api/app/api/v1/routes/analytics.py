from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.deps import get_actor_context
from app.controls.schemas import ActorContext, Capability
from app.evaluation.schemas import EvaluationResponse, EvaluationRunRequest
from app.evaluation.service import (
    EvaluationConflictError,
    EvaluationNotFoundError,
    EvaluationService,
)
from app.graph.schemas import LifecycleGraph
from app.graph.service import GraphNotFoundError, LifecycleGraphService
from app.patterns.schemas import PatternResponse
from app.patterns.service import PatternNotFoundError, PatternService
from app.repositories.factory import get_repository

router = APIRouter()
repository = get_repository()
graph_service = LifecycleGraphService(repository)
pattern_service = PatternService(repository)
evaluation_service = EvaluationService(repository)


@router.get("/exceptions/{exception_id}/graph", response_model=LifecycleGraph)
def get_exception_graph(
    exception_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> LifecycleGraph:
    _require(context, Capability.EXCEPTION_READ)
    try:
        return graph_service.build(context.organization_id, exception_id)
    except GraphNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Exception does not exist"}) from error


@router.get("/patterns", response_model=list[PatternResponse])
def list_patterns(
    context: Annotated[ActorContext, Depends(get_actor_context)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[PatternResponse]:
    _require(context, Capability.ANALYTICS_READ)
    return pattern_service.list(context.organization_id, limit)


@router.get("/patterns/{pattern_id}", response_model=PatternResponse)
def get_pattern(
    pattern_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> PatternResponse:
    _require(context, Capability.ANALYTICS_READ)
    try:
        return pattern_service.get(context.organization_id, pattern_id)
    except PatternNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Pattern does not exist"}) from error


@router.post("/evaluation/run", response_model=EvaluationResponse)
def run_evaluation(
    payload: EvaluationRunRequest,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EvaluationResponse:
    _require(context, Capability.ANALYTICS_READ)
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"})
    try:
        return evaluation_service.run(context.organization_id, payload, idempotency_key)
    except EvaluationConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}) from error


@router.get("/evaluation/latest", response_model=EvaluationResponse)
def get_latest_evaluation(
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> EvaluationResponse:
    _require(context, Capability.ANALYTICS_READ)
    try:
        return evaluation_service.latest(context.organization_id)
    except EvaluationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Evaluation does not exist"}) from error


def _require(context: ActorContext, capability: Capability) -> None:
    if capability not in context.capabilities:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"})
