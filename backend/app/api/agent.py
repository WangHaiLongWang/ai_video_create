"""Agent API — LLM-driven workflow generation and modification."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.domain.graph_validation import (
    extract_nodes_edges_from_spec,
    raise_if_invalid,
)
from backend.app.models import (
    AgentRequest, WorkflowSpec,
    ModifyRequest, ExplainRequest, ApplyPatchRequest,
    GraphPatch,
)
from backend.app.services.agent import get_agent_service
from backend.app.repositories.workflows import get_workflow, update_workflow
from backend.app.db.connection import get_connection

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _generate_diff(spec: WorkflowSpec, patch: GraphPatch) -> str:
    """Generate a human-readable diff summary for a GraphPatch."""
    lines: list[str] = []
    if patch.add_nodes:
        lines.append(f"+ 新增 {len(patch.add_nodes)} 个节点: "
                     f"{', '.join(n.data.label for n in patch.add_nodes)}")
    if patch.remove_nodes:
        lines.append(f"- 删除 {len(patch.remove_nodes)} 个节点: "
                     f"{', '.join(patch.remove_nodes)}")
    if patch.update_nodes:
        lines.append(f"~ 更新 {len(patch.update_nodes)} 个节点: "
                     f"{', '.join(u.id for u in patch.update_nodes)}")
    if patch.add_edges:
        lines.append(f"+ 新增 {len(patch.add_edges)} 条连线")
    if patch.remove_edges:
        lines.append(f"- 删除 {len(patch.remove_edges)} 条连线")
    if not lines:
        lines.append("(无变更)")
    return "\n".join(lines)


def _validate_patched_spec(spec: WorkflowSpec, patch: GraphPatch) -> None:
    """Validate the result of applying a patch to a workflow spec.

    Simulates the patch application and runs graph validation on the result.
    Raises HTTPException422 if the patched graph is invalid.
    """
    # Simulate patch application: remove, then add
    remaining_nodes = [n for n in spec.nodes if n.id not in patch.remove_nodes]
    remaining_edges = [
        e for e in spec.edges
        if e.id not in patch.remove_edges
        and e.source not in patch.remove_nodes
        and e.target not in patch.remove_nodes
    ]
    new_nodes = remaining_nodes + patch.add_nodes
    new_edges = remaining_edges + patch.add_edges

    # Convert to dicts for the validator
    nodes_dicts = [n.model_dump() for n in new_nodes]
    edges_dicts = [e.model_dump() for e in new_edges]
    raise_if_invalid(nodes_dicts, edges_dicts)


def _check_destructive(patch: GraphPatch) -> list[str]:
    """Return warnings for destructive operations in a patch."""
    warnings: list[str] = []
    if patch.remove_nodes:
        warnings.append(f"将删除 {len(patch.remove_nodes)} 个节点")
    if patch.remove_edges:
        warnings.append(f"将删除 {len(patch.remove_edges)} 条连线")
    return warnings


@router.post("/generate", response_model=WorkflowSpec)
async def generate_workflow(request: AgentRequest) -> WorkflowSpec:
    """从提示词生成工作流。"""
    service = get_agent_service()
    spec = await service.generate_from_prompt(request.prompt)

    # Validate before saving
    spec_dict = spec.model_dump()
    nodes, edges = extract_nodes_edges_from_spec(spec_dict)
    raise_if_invalid(nodes, edges)

    # 保存到数据库
    from backend.app.repositories.workflows import create_workflow
    create_workflow(spec_dict, name=spec.name)

    return spec


@router.post("/generate-preview")
async def generate_preview(request: AgentRequest) -> dict:
    """生成工作流预览（不写库）。"""
    service = get_agent_service()
    spec = await service.generate_from_prompt(request.prompt)
    spec_dict = spec.model_dump()
    nodes, edges = extract_nodes_edges_from_spec(spec_dict)
    raise_if_invalid(nodes, edges)
    return {
        "status": "ok",
        "spec": spec_dict,
        "warnings": [],
        "destructive": False,
    }


@router.post("/modify")
async def modify_workflow(request: ModifyRequest) -> dict:
    """修改工作流（返回 GraphPatch，待确认）。"""
    # 获取当前工作流
    conn = get_connection()
    row = conn.execute(
        "SELECT spec_json FROM workflows WHERE id = ?", (request.workflow_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")

    import json
    spec_dict = json.loads(row["spec_json"])
    spec = WorkflowSpec(**spec_dict)

    service = get_agent_service()
    patch = await service.modify_workflow(spec, request.instruction)

    return {
        "status": "ok",
        "patch": patch.model_dump(),
        "workflow_id": request.workflow_id,
    }


@router.post("/modify-preview")
async def modify_preview(request: ModifyRequest) -> dict:
    """修改工作流预览（返回 GraphPatch）。"""
    # 获取当前工作流
    conn = get_connection()
    row = conn.execute(
        "SELECT spec_json FROM workflows WHERE id = ?", (request.workflow_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")

    import json
    spec_dict = json.loads(row["spec_json"])
    spec = WorkflowSpec(**spec_dict)

    service = get_agent_service()
    patch = await service.modify_workflow(spec, request.instruction)

    # Validate the patched result before returning
    _validate_patched_spec(spec, patch)

    return {
        "status": "ok",
        "patch": patch.model_dump(),
        "diff": _generate_diff(spec, patch),
        "warnings": _check_destructive(patch),
        "destructive": len(patch.remove_nodes) > 0 or len(patch.remove_edges) > 0,
    }


@router.post("/explain")
async def explain_workflow(request: ExplainRequest) -> dict:
    """解释工作流功能。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT spec_json FROM workflows WHERE id = ?", (request.workflow_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")

    import json
    spec_dict = json.loads(row["spec_json"])
    spec = WorkflowSpec(**spec_dict)

    service = get_agent_service()
    explanation = await service.explain_workflow(spec)

    return {
        "status": "ok",
        "explanation": explanation,
        "workflow_id": request.workflow_id,
    }


@router.post("/apply-patch", response_model=WorkflowSpec)
async def apply_patch(request: ApplyPatchRequest) -> WorkflowSpec:
    """应用 GraphPatch 到工作流。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT spec_json, version FROM workflows WHERE id = ?", (request.workflow_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")

    import json
    spec_dict = json.loads(row["spec_json"])
    spec = WorkflowSpec(**spec_dict)
    version = row["version"]

    # Use expected_version if provided, otherwise use current version
    if request.expected_version is not None and request.expected_version != version:
        raise HTTPException(
            409,
            f"版本冲突：期望 v{request.expected_version}，实际 v{version}",
        )

    patch = request.patch

    # 应用 patch
    try:
        patch.validate_no_conflicts()
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 删除节点
    remaining_nodes = [n for n in spec.nodes if n.id not in patch.remove_nodes]
    remaining_edges = [
        e for e in spec.edges
        if e.id not in patch.remove_edges
        and e.source not in patch.remove_nodes
        and e.target not in patch.remove_nodes
    ]

    # 更新节点
    update_map = {u.id: u for u in patch.update_nodes}
    for node in remaining_nodes:
        if node.id in update_map:
            u = update_map[node.id]
            if u.label is not None:
                node.data.label = u.label
            if u.config is not None:
                node.data.config = u.config

    # 添加新节点
    new_nodes = remaining_nodes + patch.add_nodes
    new_edges = remaining_edges + patch.add_edges

    # 构建新 spec
    new_spec = WorkflowSpec(
        id=spec.id,
        name=spec.name,
        nodes=new_nodes,
        edges=new_edges,
    )

    # Validate the patched graph before saving
    new_spec_dict = new_spec.model_dump()
    nodes, edges = extract_nodes_edges_from_spec(new_spec_dict)
    raise_if_invalid(nodes, edges)

    # 保存到数据库
    try:
        update_workflow(spec.id, new_spec.model_dump(), version)
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")

    return new_spec
