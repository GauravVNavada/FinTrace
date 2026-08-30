from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_organization_id
from app.domain.schemas import ExceptionStatus, ExceptionSummary, Severity
from app.repositories.factory import get_repository

router = APIRouter()


@router.get("", response_model=list[ExceptionSummary])
def list_exceptions(
    organization_id: Annotated[str, Depends(get_organization_id)],
    severity: Annotated[Severity | None, Query()] = None,
    status: Annotated[ExceptionStatus | None, Query()] = None,
) -> list[ExceptionSummary]:
    items = get_repository().list_exceptions(organization_id)
    return [item for item in items if (severity is None or item.severity == severity) and (status is None or item.status == status)]
