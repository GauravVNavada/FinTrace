from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import get_organization_id
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
    organization_id: Annotated[str, Depends(get_organization_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InvestigationResponse | JSONResponse:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"})
    try:
        response = investigation_service.start(organization_id, exception_id, idempotency_key)
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
    organization_id: Annotated[str, Depends(get_organization_id)],
) -> InvestigationResponse:
    try:
        return investigation_service.get(organization_id, investigation_id)
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Investigation does not exist"}) from error


@router.get("/investigations/{investigation_id}/tool-calls", response_model=list[ToolCall])
def get_tool_calls(
    investigation_id: str,
    organization_id: Annotated[str, Depends(get_organization_id)],
) -> list[ToolCall]:
    try:
        return investigation_service.get_tool_calls(organization_id, investigation_id)
    except InvestigationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Investigation does not exist"}) from error
