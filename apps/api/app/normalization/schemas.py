from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    organization_id: str
    financial_investigation_id: str
    version_no: int = Field(gt=0)
    status: str
    record_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    created_at: datetime


class NormalizedRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_file_id: str
    source_row_number: int = Field(gt=1)
    source_record_id: str | None
    source_type: str
    values: dict[str, str | int | None]
    lineage: dict[str, dict[str, str | int | None]]
