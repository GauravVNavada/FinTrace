from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_organization_id
from app.domain.lifecycle import LifecycleNotFoundError
from app.domain.schemas import LifecycleResponse
from app.repositories.demo import demo_repository

router = APIRouter()


@router.get("/{order_id}", response_model=LifecycleResponse)
def get_lifecycle(order_id: str, organization_id: Annotated[str, Depends(get_organization_id)]) -> LifecycleResponse:
    try:
        lifecycle = demo_repository.lifecycle(organization_id, order_id)
    except LifecycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lifecycle not found") from error
    return LifecycleResponse(
        organization_id=organization_id,
        order=lifecycle.order,
        payments=list(lifecycle.payments),
        settlements=list(lifecycle.settlements),
        invoices=list(lifecycle.invoices),
        refunds=list(lifecycle.refunds),
        inventory_movements=list(lifecycle.inventory_movements),
        employee_actions=list(lifecycle.employee_actions),
    )
