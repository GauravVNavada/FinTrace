from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.api.deps import get_actor_context
from app.controls.schemas import ActorContext, Capability
from app.domain.schemas import ExceptionStatus, ExceptionSummary, Severity
from app.repositories.factory import get_repository

router = APIRouter()


@router.get("", response_model=list[ExceptionSummary])
def list_exceptions(
    context: Annotated[ActorContext, Depends(get_actor_context)],
    severity: Annotated[Severity | None, Query()] = None,
    status: Annotated[ExceptionStatus | None, Query()] = None,
) -> list[ExceptionSummary]:
    _require(context, Capability.EXCEPTION_READ)
    items = get_repository().list_exceptions(context.organization_id)
    return [item for item in items if (severity is None or item.severity == severity) and (status is None or item.status == status)]


@router.get("/{exception_id}", response_model=ExceptionSummary)
def get_exception(exception_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]) -> ExceptionSummary:
    _require(context, Capability.EXCEPTION_READ)
    item = get_repository().get_exception(context.organization_id, exception_id)
    if item is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail={"code": "RESOURCE_NOT_FOUND", "message": "Exception does not exist"})
    return item


def _require(context: ActorContext, capability: Capability) -> None:
    if capability not in context.capabilities:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"})
