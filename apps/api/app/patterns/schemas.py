from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PatternResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    exception_type: str
    title: str
    occurrence_count: int = Field(ge=2)
    associated_exposure: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    location: str
    workflow: str
    observation: str
    prevention_recommendation: str
    severity: str
    member_order_ids: list[str] = Field(max_length=100)
