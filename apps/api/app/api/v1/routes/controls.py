from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.deps import get_actor_context
from app.controls.schemas import (
    ActorContext,
    ApprovalResponse,
    AuditEventResponse,
    Capability,
    Decision,
    ResolutionRequestCreate,
    ResolutionRequestResponse,
)
from app.controls.service import (
    ControlConflictError,
    ControlForbiddenError,
    ControlNotFoundError,
    ControlsService,
    ControlStateError,
)
from app.repositories.demo import demo_repository

router = APIRouter()
controls_service = ControlsService(demo_repository)


@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    context: Annotated[ActorContext, Depends(get_actor_context)],
    resource_id: Annotated[str | None, Query(max_length=128)] = None,
) -> list[AuditEventResponse]:
    if Capability.AUDIT_READ not in context.capabilities:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Audit access is restricted"})
    events = (
        demo_repository.audit_events(context.organization_id, resource_id)
        if resource_id
        else demo_repository.audit_events_for_organization(context.organization_id)
    )
    public_fields = ("event_id", "organization_id", "actor_id", "action", "resource_id", "correlation_id", "created_at")
    return [AuditEventResponse.model_validate({field: event[field] for field in public_fields}) for event in events]


@router.post("/exceptions/{exception_id}/resolution-request", response_model=ResolutionRequestResponse)
def request_resolution(
    exception_id: str,
    payload: ResolutionRequestCreate,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ResolutionRequestResponse:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"})
    try:
        return controls_service.request_resolution(context, exception_id, payload.action_code, idempotency_key)
    except ControlNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Exception does not exist"}) from error
    except ControlForbiddenError as error:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(error)}) from error
    except ControlConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}) from error
    except (ControlStateError, ValueError) as error:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": str(error)}) from error


@router.post("/approvals/{request_id}/approve", response_model=ApprovalResponse)
def approve(
    request_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApprovalResponse:
    return _decide(request_id, context, idempotency_key, Decision.APPROVED)


@router.post("/approvals/{request_id}/reject", response_model=ApprovalResponse)
def reject(
    request_id: str,
    context: Annotated[ActorContext, Depends(get_actor_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ApprovalResponse:
    return _decide(request_id, context, idempotency_key, Decision.REJECTED)


def _decide(request_id: str, context: ActorContext, idempotency_key: str | None, decision: Decision) -> ApprovalResponse:
    if idempotency_key is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"})
    try:
        return controls_service.approve(context, request_id, idempotency_key) if decision == Decision.APPROVED else controls_service.reject(context, request_id, idempotency_key)
    except ControlNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "Approval request does not exist"}) from error
    except ControlForbiddenError as error:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(error)}) from error
    except ControlConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(error)}) from error
    except (ControlStateError, ValueError) as error:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "message": str(error)}) from error
