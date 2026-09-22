"""Modules API — module definition management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.module_definition import ModuleDefinition
from backend.app.services.module_registry import get_module_registry

router = APIRouter(prefix="/api/modules", tags=["modules"])


@router.get("")
async def list_modules(
    status: str | None = Query(default=None, description="Filter by status"),
    capability: str | None = Query(default=None, description="Filter by capability"),
) -> list[ModuleDefinition]:
    """列出所有模块定义。"""
    registry = get_module_registry()
    return registry.list_modules(status=status, capability=capability)


@router.get("/{module_id}")
async def get_module(module_id: str) -> ModuleDefinition:
    """获取模块详情（最新版本）。"""
    registry = get_module_registry()
    module = registry.get_module(module_id)
    if not module:
        raise HTTPException(404, f"模块不存在: {module_id}")
    return module


@router.get("/{module_id}/versions/{version}")
async def get_module_version(module_id: str, version: str) -> ModuleDefinition:
    """获取指定版本的模块。"""
    registry = get_module_registry()
    module = registry.get_module(module_id, version=version)
    if not module:
        raise HTTPException(404, f"模块版本不存在: {module_id}@{version}")
    return module
