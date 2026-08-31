from pydantic import BaseModel, ConfigDict, Field


class FinancialInvestigationPatternResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    financial_investigation_id: str
    exception_type: str
    occurrence_count: int = Field(ge=2)
    associated_exposure_minor: int = Field(ge=0)
    member_order_ids: list[str] = Field(min_length=2, max_length=10_000)
    advisory: bool = True
    observation: str
