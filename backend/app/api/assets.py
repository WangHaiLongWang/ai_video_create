"""Assets API — 资产管理和血缘查询。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.repositories.assets import (
    list_assets, get_asset, get_asset_lineage,
    get_asset_stats, delete_asset, AssetNotFoundError,
)

router = APIRouter(prefix="/api/assets", tags=["assets"])


class AssetResponse(BaseModel):
    id: str
    execution_id: str
    node_id: str
    task_id: str
    scene_id: str | None = None
    asset_type: str
    file_path: str
    file_size: int = 0
    mime_type: str = ""
    provider: str = ""
    model: str = ""
    source_asset_ids: list[str] = []
    metadata: dict = {}
    created_at: str = ""


@router.get("")
def list_assets_api(
    execution_id: str | None = Query(None),
    node_id: str | None = Query(None),
    asset_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict]:
    """列出资产。"""
    return list_assets(execution_id=execution_id, node_id=node_id,
                       asset_type=asset_type, limit=limit)


@router.get("/stats")
def get_stats_api(
    execution_id: str | None = Query(None),
) -> dict:
    """资产统计。"""
    return get_asset_stats(execution_id=execution_id)


@router.get("/{asset_id}")
def get_asset_api(asset_id: str) -> dict:
    """获取单个资产。"""
    try:
        return get_asset(asset_id)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail=f"资产 {asset_id} 不存在")


@router.get("/{asset_id}/lineage")
def get_lineage_api(asset_id: str) -> dict:
    """获取资产血缘链。"""
    # 先检查资产是否存在
    try:
        get_asset(asset_id)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail=f"资产 {asset_id} 不存在")

    lineage = get_asset_lineage(asset_id)
    return {"asset_id": asset_id, "lineage": lineage}


@router.delete("/{asset_id}", status_code=204)
def delete_asset_api(asset_id: str) -> None:
    """删除资产。"""
    try:
        delete_asset(asset_id)
    except AssetNotFoundError:
        raise HTTPException(status_code=404, detail=f"资产 {asset_id} 不存在")
