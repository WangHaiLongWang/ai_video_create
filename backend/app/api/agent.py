"""Agent API — LLM-driven workflow generation and modification."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

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
from backend.app.services.agent_diff import (
    check_destructive as _check_destructive,
    generate_diff as _generate_diff,
)
from backend.app.services import agent_trace
from backend.app.repositories.workflows import get_workflow, update_workflow
from backend.app.db.connection import get_connection

router = APIRouter(prefix="/api/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Trace query error envelopes (same shape as graph_validation.build_422_response)
# ---------------------------------------------------------------------------

def _trace_error_body(code: str, message: str, errors: list[dict] | None = None) -> dict:
    """Build the structured error envelope reused from build_422_response."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if errors is not None:
        body["error"]["details"] = {"errors": errors}
    return body


def _trace_validation_error(errors: list[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_trace_error_body(
            "TRACE_QUERY_INVALID",
            f"轨迹查询参数无效（{len(errors)} 个错误）",
            errors,
        ),
    )


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


@router.post("/generate", response_model=WorkflowSpec, deprecated=True)
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


@router.post("/generate-preview", deprecated=True)
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


@router.post("/modify", deprecated=True)
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
    patch = await service.modify_workflow(
        spec, request.instruction, workflow_id=request.workflow_id
    )

    return {
        "status": "ok",
        "patch": patch.model_dump(),
        "workflow_id": request.workflow_id,
    }


@router.post("/modify-preview", deprecated=True)
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
    patch = await service.modify_workflow(
        spec, request.instruction, workflow_id=request.workflow_id
    )

    # Validate the patched result before returning
    _validate_patched_spec(spec, patch)

    return {
        "status": "ok",
        "patch": patch.model_dump(),
        "diff": _generate_diff(spec, patch),
        "warnings": _check_destructive(patch),
        "destructive": len(patch.remove_nodes) > 0 or len(patch.remove_edges) > 0,
    }


@router.post("/explain", deprecated=True)
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


@router.post("/apply-patch", response_model=WorkflowSpec, deprecated=True)
async def apply_patch(request: ApplyPatchRequest) -> WorkflowSpec:
    """应用 GraphPatch 到工作流。"""
    patch = request.patch
    diff_summary = agent_trace.summarize_graph_patch(patch)

    with agent_trace.trace_operation(
        agent_trace.TRACE_KIND_APPLY,
        workflow_id=request.workflow_id,
        prompt=patch.description or "",
    ) as tr:
        tr.set_module_diff_summary(diff_summary)
        try:
            new_spec = _apply_patch_impl(request)
        except HTTPException as exc:
            tr.set_status("error", error_code=f"HTTP_{exc.status_code}")
            raise

        agent_trace.safe_finish(tr, module_diff_summary=diff_summary)
        agent_trace.emit_agent_audit(
            agent_trace.AUDIT_APPLY,
            prompt_hash=tr.prompt_hash,
            module_diff_summary=diff_summary,
            repair_count=tr.repair_count,
            trace_id=tr.trace_id or None,
        )
        return new_spec


def _apply_patch_impl(request: ApplyPatchRequest) -> WorkflowSpec:
    """Apply a GraphPatch to a workflow (persistence + validation)."""
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
    try:
        raise_if_invalid(nodes, edges)
    except HTTPException:
        agent_trace.safe_add_step(
            None, "validate", "graph_validation", "error", 0, {}
        )
        raise
    agent_trace.safe_add_step(None, "validate", "graph_validation", "ok", 0, {})

    # 保存到数据库
    try:
        update_workflow(spec.id, new_spec.model_dump(), version)
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")

    return new_spec


# ---------------------------------------------------------------------------
# Agent Trace queries (pinned contract)
# ---------------------------------------------------------------------------

@router.get("/traces")
async def list_agent_traces(
    workflow_id: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Any:
    """列出 agent 轨迹摘要。

    Query: workflow_id?  kind?  limit? (default 50, max 200)  offset? (default 0)
    200 -> { "traces": [TraceSummary], "total": int }
    """
    errors: list[dict] = []
    if kind is not None and kind not in agent_trace.TRACE_KINDS:
        errors.append({
            "code": "TRACE_KIND_INVALID",
            "message": f"kind 必须是 {'/'.join(agent_trace.TRACE_KINDS)} 之一",
        })
    if limit < 1 or limit > 200:
        errors.append({
            "code": "TRACE_LIMIT_INVALID",
            "message": "limit 必须在 1..200 之间",
        })
    if offset < 0:
        errors.append({
            "code": "TRACE_OFFSET_INVALID",
            "message": "offset 不能为负数",
        })
    if errors:
        return _trace_validation_error(errors)

    return agent_trace.list_traces(
        workflow_id=workflow_id, kind=kind, limit=limit, offset=offset
    )


@router.get("/traces/{trace_id}")
async def get_agent_trace(trace_id: str) -> Any:
    """获取单条轨迹详情。

    200 -> TraceDetail
    404 -> { "error": { "code": "TRACE_NOT_FOUND", "message": str } }
    """
    detail = agent_trace.get_trace(trace_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content=_trace_error_body(
                "TRACE_NOT_FOUND", f"轨迹不存在: {trace_id}"
            ),
        )
    return detail
