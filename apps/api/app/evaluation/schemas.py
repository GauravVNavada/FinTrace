from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    orders: int = Field(default=1000, ge=1, le=10000)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    anomaly_rate: float = Field(default=0.30, ge=0, le=1)


class EvaluationReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycles: int = Field(ge=0)
    auto_reconciled: int = Field(ge=0)
    exceptions: int = Field(ge=0)
    ambiguous: int = Field(ge=0)
    match_rate: float = Field(ge=0, le=100)
    match_precision: float = Field(ge=0, le=100)
    exception_recall: float = Field(ge=0, le=100)
    throughput_per_second: float = Field(ge=0)
    unresolved_exceptions: int = Field(ge=0)


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    organization_id: str
    seed: int
    anomaly_rate: float = Field(ge=0, le=1)
    report: EvaluationReportResponse
    created_at: datetime
