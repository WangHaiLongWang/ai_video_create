from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Position(BaseModel):
    x: float
    y: float


class NodeData(BaseModel):
    label: str
    description: str
    kind: str
    inputType: str | None = None
    outputType: str | None = None
    status: str = "idle"
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    id: str
    type: str = "studio"
    position: Position
    data: NodeData


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str = "smoothstep"


class WorkflowSpec(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    id: str
    name: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkflowSpec":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("节点 ID 必须唯一")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(f"连线 {edge.id} 引用了不存在的节点")
            source = next(node for node in self.nodes if node.id == edge.source)
            target = next(node for node in self.nodes if node.id == edge.target)
            if source.data.outputType != target.data.inputType:
                raise ValueError(f"连线 {edge.id} 的端口类型不兼容")
        return self


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)

