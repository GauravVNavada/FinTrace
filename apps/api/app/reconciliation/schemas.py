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
    records_expected: int = Field(default=0, ge=0)
    records_loaded: int = Field(default=0, ge=0)
    records_consumed: int = Field(default=0, ge=0)
    orphan_record_count: int = Field(default=0, ge=0)
    rejected_record_count: int = Field(default=0, ge=0)
    failure_reason: str | None = None
    is_stale: bool = False
    stale_reason: str | None = None
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
    exposure_category: str = "DATA_QUALITY"


class ReconciliationResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    run_id: str
    order_id: str
    status: str
    exception_type: str | None
    severity: str
    exposure_minor: int = Field(ge=0)
    exposure_category: str = "DATA_QUALITY"
    findings: list[ReconciliationFindingResponse]
