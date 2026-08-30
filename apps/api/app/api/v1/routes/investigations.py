from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import get_actor_context
from app.controls.schemas import ActorContext, Capability
from app.core.config import get_settings
from app.investigations.provider import get_ai_client
from app.investigations.schemas import InvestigationResponse, ToolCall
from app.investigations.service import (
    IdempotencyConflictError,
    InvestigationNotFoundError,
    InvestigationService,
)
from app.repositories.factory import get_repository

router = APIRouter()
investigation_service = InvestigationService(get_repository(), get_ai_client(get_settings().ai_provider))


@router.post("/exceptions/{exception_id}/investigations", response_model=InvestigationResponse, status_code=status.HTTP_200_OK)
def start_investigation(
    exception_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvestigationResponse | JSONResponse:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"})
    try:
        if Capability.EXCEPTION_INVESTIGATE not in context.capabilities:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"})
        response = investigation_service.start(context.organization_id, exception_id, idempotency_key)
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Exception does not exist"}) from error
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}) from error
    if response.status == "FAILED":
        return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
    return response


@router.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(
    investigation_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> InvestigationResponse:
    if Capability.EXCEPTION_READ not in context.capabilities:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"})
    try:
        return investigation_service.get(context.organization_id, investigation_id)
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Investigation does not exist"}) from error


@router.get("/investigations/{investigation_id}/tool-calls", response_model=list[ToolCall])
def get_tool_calls(
    investigation_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
) -> list[ToolCall]:
    if Capability.EXCEPTION_READ not in context.capabilities:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"})
    try:
        return investigation_service.get_tool_calls(context.organization_id, investigation_id)
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Investigation does not exist"}) from error
