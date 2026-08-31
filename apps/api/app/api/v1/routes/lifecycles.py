from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_actor_context
from app.controls.schemas import ActorContext, Capability
from app.domain.lifecycle import LifecycleNotFoundError
from app.domain.schemas import LifecycleResponse
from app.repositories.factory import get_repository

router = APIRouter()


@router.get("/{order_id}", response_model=LifecycleResponse)
def get_lifecycle(
    order_id: str, context: Annotated[ActorContext, Depends(get_actor_context)]
) -> LifecycleResponse:
    if Capability.EXCEPTION_READ not in context.capabilities:
        raise HTTPException(
            status_code=403, detail={"code": "FORBIDDEN", "message": "Capability is required"}
        )
    try:
        lifecycle = get_repository().lifecycle(context.organization_id, order_id)
    except LifecycleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lifecycle not found"
        ) from error
    return LifecycleResponse(
        organization_id=context.organization_id,
        order=lifecycle.order,
        payments=list(lifecycle.payments),
        settlements=list(lifecycle.settlements),
        invoices=list(lifecycle.invoices),
        refunds=list(lifecycle.refunds),
        inventory_movements=list(lifecycle.inventory_movements),
        employee_actions=list(lifecycle.employee_actions),
    )
