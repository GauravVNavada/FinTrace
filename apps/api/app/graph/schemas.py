from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeState(StrEnum):
    CONFIRMED = "CONFIRMED"
    MISSING = "MISSING"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    entity_type: str
    label: str
    state: GraphNodeState
    amount_minor: int | None = Field(default=None, ge=0)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relationship: str


class LifecycleGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exception_id: str
    organization_id: str
    nodes: list[GraphNode] = Field(max_length=100)
    edges: list[GraphEdge] = Field(max_length=200)
