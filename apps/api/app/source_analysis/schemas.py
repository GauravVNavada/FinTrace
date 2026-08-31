from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.financial_investigations.schemas import SourceType


class InferredType(StrEnum):
    EMPTY = "EMPTY"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    STRING = "STRING"


class AnalysisProviderStatus(StrEnum):
    OFFLINE_DETERMINISTIC = "OFFLINE_DETERMINISTIC"
    AI_PROVIDER = "AI_PROVIDER"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"


class MappingStatus(StrEnum):
    PROPOSED = "PROPOSED"
    EDITED = "EDITED"
    CONFIRMED = "CONFIRMED"


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    inferred_type: InferredType
    non_empty_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    sample_values: list[str] = Field(default_factory=list, max_length=5)
    min_value: str | None = Field(default=None, max_length=200)
    max_value: str | None = Field(default=None, max_length=200)


class SourceAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    organization_id: str
    financial_investigation_id: str
    source_file_id: str
    headers: list[str] = Field(max_length=200)
    sample_rows: list[dict[str, str | None]] = Field(max_length=20)
    columns: list[ColumnProfile] = Field(max_length=200)
    source_type: SourceType
    classification_confidence: float = Field(ge=0, le=1)
    reasoning_summary: str = Field(min_length=1, max_length=500)
    provider_status: AnalysisProviderStatus
    provider: str = "offline-deterministic"
    model: str = "none"
    analyzed_at: datetime


class SourceTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType


class MappingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    organization_id: str
    financial_investigation_id: str
    source_file_id: str
    source_column: str = Field(min_length=1, max_length=200)
    canonical_field: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0, le=1)
    required: bool
    inferred_type: InferredType
    ignored: bool
    status: MappingStatus
    updated_at: datetime


class MappingEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_field: str | None = Field(default=None, max_length=100)
    ignored: bool = False


class MappingConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_investigation_id: str
    source_file_id: str
    status: MappingStatus
    confirmed_mapping_count: int = Field(ge=0)
    ignored_column_count: int = Field(ge=0)
