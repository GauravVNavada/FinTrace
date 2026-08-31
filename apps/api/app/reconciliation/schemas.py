from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version_id: str | None = None


class ReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    organization_id: str
    financial_investigation_id: str
    dataset_version_id: str
    status: str
    lifecycle_count: int = Field(ge=0)
    reconciled_count: int = Field(ge=0)
    exception_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    open_exposure_minor: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime | None


class ReconciliationFindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    exposure_minor: int = Field(ge=0)


class ReconciliationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    order_id: str
    status: str
    exception_type: str | None
    severity: str
    exposure_minor: int = Field(ge=0)
    findings: list[ReconciliationFindingResponse]
