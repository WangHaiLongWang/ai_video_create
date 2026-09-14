"""Agent API — LLM-driven workflow generation and modification."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.models import (
    AgentRequest, WorkflowSpec,
    ModifyRequest, ExplainRequest, ApplyPatchRequest,
    GraphPatch,
)
from backend.app.services.agent import get_agent_service
from backend.app.repositories.workflows import get_workflow, update_workflow
from backend.app.db.connection import get_connection

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/generate", response_model=WorkflowSpec)
async def generate_workflow(request: AgentRequest) -> WorkflowSpec:
    """从提示词生成工作流。"""
    service = get_agent_service()
    spec = await service.generate_from_prompt(request.prompt)

    # 保存到数据库
    from backend.app.repositories.workflows import create_workflow
    create_workflow(spec.model_dump(), name=spec.name)

    return spec


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

    # 保存到数据库
    try:
        update_workflow(spec.id, new_spec.model_dump(), version)
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")

    return new_spec
