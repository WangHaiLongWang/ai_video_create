"""Template API — workflow template management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.models import WorkflowSpec, TemplateInfo, TemplateDetail
from backend.app.services.templates import get_template_service

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateFromTemplateRequest(BaseModel):
    name: str = ""
    prompt: str = ""


class SaveAsTemplateRequest(BaseModel):
    workflow_id: str
    name: str
    description: str = ""
    tags: list[str] = []


@router.get("")
async def list_templates() -> list[TemplateInfo]:
    """列出所有模板。"""
    service = get_template_service()
    return service.list_templates()


@router.get("/{template_id}")
async def get_template(template_id: str) -> TemplateDetail:
    """获取模板详情。"""
    service = get_template_service()
    detail = service.get_template(template_id)
    if not detail:
        raise HTTPException(404, f"模板不存在: {template_id}")
    return detail


@router.post("/{template_id}/create", response_model=WorkflowSpec)
async def create_from_template(template_id: str, request: CreateFromTemplateRequest | None = None) -> WorkflowSpec:
    """从模板创建工作流。"""
    service = get_template_service()
    params = {}
    if request:
        params = {"name": request.name, "prompt": request.prompt}

    spec = service.create_from_template(template_id, params or None)
    if not spec:
        raise HTTPException(404, f"模板不存在: {template_id}")

    # 保存到数据库
    from backend.app.repositories.workflows import create_workflow
    conn_spec = spec.model_dump()
    create_workflow(conn_spec, name=spec.name)

    return spec


@router.post("/save")
async def save_as_template(request: SaveAsTemplateRequest) -> dict[str, str]:
    """保存工作流为模板。"""
    from backend.app.db.connection import get_connection
    import json

    conn = get_connection()
    row = conn.execute(
        "SELECT spec_json FROM workflows WHERE id = ?", (request.workflow_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "工作流不存在")

    spec_dict = json.loads(row["spec_json"])
    spec = WorkflowSpec(**spec_dict)

    service = get_template_service()
    template_id = service.save_as_template(spec, request.name, request.description, request.tags)

    return {"status": "ok", "template_id": template_id}
