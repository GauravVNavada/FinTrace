from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RelationshipStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    organization_id: str
    financial_investigation_id: str
    source_file_id: str
    target_source_file_id: str
    join_fields: list[str] = Field(min_length=1, max_length=20)
    evidence_summary: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    confidence_label: str = "LOW"
    left_columns: list[str] = Field(default_factory=list, max_length=20)
    right_columns: list[str] = Field(default_factory=list, max_length=20)
    value_overlap_percent: float = Field(default=0, ge=0, le=100)
    duplicate_key_rate_percent: float = Field(default=0, ge=0, le=100)
    cardinality: str = "UNKNOWN"
    type_compatibility: str = "UNKNOWN"
    temporal_consistency_percent: float | None = Field(default=None, ge=0, le=100)
    amount_agreement_percent: float | None = Field(default=None, ge=0, le=100)
    status: RelationshipStatus
    updated_at: datetime


class RelationshipDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[
        RelationshipStatus.ACCEPTED, RelationshipStatus.REJECTED, RelationshipStatus.EDITED
    ]
