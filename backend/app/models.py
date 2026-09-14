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


class NodeUpdate(BaseModel):
    """用于 GraphPatch 的节点更新。"""
    id: str
    label: str | None = None
    config: dict[str, Any] | None = None


class GraphPatch(BaseModel):
    """工作流修改补丁 — LLM 生成后由用户确认应用。"""
    description: str = ""
    add_nodes: list[WorkflowNode] = Field(default_factory=list)
    remove_nodes: list[str] = Field(default_factory=list)
    update_nodes: list[NodeUpdate] = Field(default_factory=list)
    add_edges: list[WorkflowEdge] = Field(default_factory=list)
    remove_edges: list[str] = Field(default_factory=list)

    def validate_no_conflicts(self) -> None:
        """校验 patch 内部无冲突。"""
        add_ids = [n.id for n in self.add_nodes]
        if len(add_ids) != len(set(add_ids)):
            raise ValueError("add_nodes 中存在重复 ID")
        overlap = set(add_ids) & set(self.remove_nodes)
        if overlap:
            raise ValueError(f"同时添加和删除节点: {overlap}")


class ModifyRequest(BaseModel):
    """修改工作流请求。"""
    workflow_id: str
    instruction: str = Field(min_length=1, max_length=2000)


class ExplainRequest(BaseModel):
    """解释工作流请求。"""
    workflow_id: str


class ApplyPatchRequest(BaseModel):
    """应用 GraphPatch 请求。"""
    workflow_id: str
    patch: GraphPatch


class TemplateInfo(BaseModel):
    """模板摘要信息。"""
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    node_count: int = 0


class TemplateDetail(BaseModel):
    """模板完整信息。"""
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    spec: WorkflowSpec

