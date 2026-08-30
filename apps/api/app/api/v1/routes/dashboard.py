from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_organization_id
from app.domain.schemas import DashboardSummary
from app.repositories.demo import demo_repository

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def get_summary(organization_id: Annotated[str, Depends(get_organization_id)]) -> DashboardSummary:
    return demo_repository.dashboard_summary(organization_id)
