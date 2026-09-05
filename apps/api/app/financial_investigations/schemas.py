from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FinancialInvestigationStatus(StrEnum):
    DRAFT = "DRAFT"
    SOURCES_UPLOADED = "SOURCES_UPLOADED"
    MAPPING_REQUIRED = "MAPPING_REQUIRED"
    RELATIONSHIP_REVIEW = "RELATIONSHIP_REVIEW"
    READY_TO_BUILD = "READY_TO_BUILD"
    PROCESSING = "PROCESSING"
    RECONCILED = "RECONCILED"
    FAILED = "FAILED"


class SourceFileStatus(StrEnum):
    UPLOADED = "UPLOADED"
    ANALYZING = "ANALYZING"
    MAPPING_REQUIRED = "MAPPING_REQUIRED"
    READY = "READY"
    FAILED = "FAILED"


class SourceType(StrEnum):
    SALES = "SALES"
    ORDERS = "ORDERS"
    PAYMENTS = "PAYMENTS"
    SETTLEMENTS = "SETTLEMENTS"
    REFUNDS = "REFUNDS"
    INVOICES = "INVOICES"
    INVENTORY_MOVEMENTS = "INVENTORY_MOVEMENTS"
    EMPLOYEE_ACTIONS = "EMPLOYEE_ACTIONS"
    UNKNOWN = "UNKNOWN"


class SampleDataRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orders: int = Field(default=25, ge=1, le=2_000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    anomaly_rate: float = Field(default=0.30, ge=0, le=1)
    scenario_types: list[str] = Field(default_factory=list, max_length=12)
    preset: str | None = Field(default=None, max_length=64)


class FinancialInvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    period_start: date
    period_end: date
    base_currency: str = Field(min_length=3, max_length=3)

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("base_currency must contain three letters")
        return normalized

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, value: date, info):
        period_start = info.data.get("period_start")
        if period_start is not None and value < period_start:
            raise ValueError("period_end must be on or after period_start")
        return value


class FinancialInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    organization_id: str
    name: str
    description: str | None
    period_start: date
    period_end: date
    base_currency: str
    status: FinancialInvestigationStatus
    created_by: str
    created_at: datetime
    updated_at: datetime
    source_file_count: int = Field(ge=0)


class SourceFileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: str
    organization_id: str
    financial_investigation_id: str
    original_filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)
    row_count: int | None = Field(default=None, ge=0)
    column_count: int | None = Field(default=None, ge=0)
    status: SourceFileStatus
    detected_source_type: SourceType | None = None
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime
    deduplicated: bool = False


class SampleDataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_investigation_id: str
    orders: int = Field(gt=0)
    seed: int = Field(ge=0)
    anomaly_rate: float = Field(ge=0, le=1)
    scenario_types: list[str]
    sources: list[SourceFileResponse]
