from typing import Annotated, cast

from fastapi import APIRouter, Depends

from app.api.deps import get_organization_id
from app.domain.schemas import DashboardSummary
from app.repositories.factory import get_repository
from app.repositories.contracts import WorkflowRepository
from app.reconciliation.schemas import ReconciliationRunResponse

router = APIRouter()


@router.get("/latest-run", response_model=ReconciliationRunResponse | None)
def get_latest_run(organization_id: Annotated[str, Depends(get_organization_id)]) -> ReconciliationRunResponse | None:
    run = cast(WorkflowRepository, get_repository()).latest_workspace_run(organization_id)
    return ReconciliationRunResponse.model_validate(run) if run else None


@router.get("/summary", response_model=DashboardSummary)
def get_summary(organization_id: Annotated[str, Depends(get_organization_id)]) -> DashboardSummary:
    return get_repository().dashboard_summary(organization_id)
