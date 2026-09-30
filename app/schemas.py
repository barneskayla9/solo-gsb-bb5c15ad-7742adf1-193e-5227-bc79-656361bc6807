from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

NodeKind = Literal["source", "junction", "sink"]
Code = Annotated[str, Field(min_length=1, max_length=128)]


def _strip(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("编号不能为空")
    return v


class NodeIn(BaseModel):
    code: Code
    kind: NodeKind
    name: str | None = None

    @field_validator("code")
    @classmethod
    def _clean_code(cls, v: str) -> str:
        return _strip(v)


class EdgeIn(BaseModel):
    code: Code
    from_code: Code
    to_code: Code
    has_valve: bool = False
    valve_closed: bool = False
    name: str | None = None

    @field_validator("code", "from_code", "to_code")
    @classmethod
    def _clean_code(cls, v: str) -> str:
        return _strip(v)


class NetworkImportRequest(BaseModel):
    nodes: list[NodeIn] = Field(default_factory=list)
    edges: list[EdgeIn] = Field(default_factory=list)


class NetworkImportResponse(BaseModel):
    version: int
    node_count: int
    edge_count: int
    message: str


class NodeOut(BaseModel):
    code: str
    kind: NodeKind
    name: str | None = None


class EdgeOut(BaseModel):
    code: str
    from_code: str
    to_code: str
    has_valve: bool
    valve_closed: bool
    name: str | None = None


class NetworkResponse(BaseModel):
    version: int
    nodes: list[NodeOut]
    edges: list[EdgeOut]


class IsolationPreviewRequest(BaseModel):
    fault_edge: Code
    proposed_closed: list[Code] = Field(default_factory=list)
    version: int = Field(..., ge=1, description="读取管网时看到的版本号")

    @field_validator("fault_edge")
    @classmethod
    def _clean_fault(cls, v: str) -> str:
        return _strip(v)

    @field_validator("proposed_closed")
    @classmethod
    def _clean_list(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v]


class IsolationResultResponse(BaseModel):
    can_isolate: bool
    fault_edge: str
    version: int
    closed_valves: list[str]
    lost_sinks: list[str]
    reachable_sinks_before: list[str]
    reachable_sinks_after: list[str]
    fault_endpoint_reachable: dict[str, bool]


class ErrorResponse(BaseModel):
    error: dict
