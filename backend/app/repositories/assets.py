"""Assets repository — 资产 CRUD 和血缘追踪。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.db.connection import get_connection


class AssetNotFoundError(Exception):
    pass


def create_asset(
    execution_id: str,
    node_id: str,
    task_id: str,
    asset_type: str,
    file_path: str,
    file_size: int = 0,
    mime_type: str = "",
    provider: str = "",
    model: str = "",
    scene_id: str | None = None,
    variant_id: str | None = None,
    source_asset_ids: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """创建资产记录。"""
    conn = get_connection()
    asset_id = f"asset-{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    conn.execute(
        "INSERT INTO assets (id, execution_id, node_id, task_id, scene_id, "
        "variant_id, asset_type, file_path, file_size, mime_type, provider, model, "
        "source_asset_ids, metadata, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            asset_id, execution_id, node_id, task_id,
            scene_id,
            variant_id,
            asset_type, file_path, file_size, mime_type,
            provider, model,
            json.dumps(source_asset_ids or [], ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
            now,
        ),
    )
    conn.commit()

    return get_asset(asset_id)


def get_asset(asset_id: str) -> dict:
    """获取单个资产。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if row is None:
        raise AssetNotFoundError(f"资产 {asset_id} 不存在")
    return _row_to_dict(row)


def list_assets(
    execution_id: str | None = None,
    node_id: str | None = None,
    asset_type: str | None = None,
    scene_id: str | None = None,
    variant_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """列出资产，支持按 execution/node/type/scene/variant 过滤。"""
    conn = get_connection()
    conditions = []
    params: list[Any] = []

    if execution_id:
        conditions.append("execution_id = ?")
        params.append(execution_id)
    if node_id:
        conditions.append("node_id = ?")
        params.append(node_id)
    if asset_type:
        conditions.append("asset_type = ?")
        params.append(asset_type)
    if scene_id:
        conditions.append("scene_id = ?")
        params.append(scene_id)
    if variant_id:
        conditions.append("variant_id = ?")
        params.append(variant_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM assets {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_asset_lineage(asset_id: str) -> list[dict]:
    """获取资产血缘链（从当前资产向上追溯所有源资产）。"""
    visited = set()
    result = []
    _trace_lineage(asset_id, visited, result)
    return result


def _trace_lineage(asset_id: str, visited: set, result: list) -> None:
    """递归追踪资产血缘。"""
    if asset_id in visited:
        return
    visited.add(asset_id)

    try:
        asset = get_asset(asset_id)
    except AssetNotFoundError:
        return

    result.append(asset)
    raw_source = asset.get("source_asset_ids", [])
    source_ids = raw_source if isinstance(raw_source, list) else json.loads(raw_source)
    for src_id in source_ids:
        _trace_lineage(src_id, visited, result)


def get_assets_by_execution_lineage(execution_id: str) -> list[dict]:
    """获取执行的所有资产，按创建时间排序（血缘链路）。"""
    return list_assets(execution_id=execution_id, limit=1000)


def delete_asset(asset_id: str) -> None:
    """删除资产记录。"""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise AssetNotFoundError(f"资产 {asset_id} 不存在")


def get_asset_stats(execution_id: str | None = None) -> dict:
    """获取资产统计信息。"""
    conn = get_connection()
    if execution_id:
        rows = conn.execute(
            "SELECT asset_type, COUNT(*) as cnt, SUM(file_size) as total_size "
            "FROM assets WHERE execution_id = ? GROUP BY asset_type",
            (execution_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT asset_type, COUNT(*) as cnt, SUM(file_size) as total_size "
            "FROM assets GROUP BY asset_type",
        ).fetchall()

    stats = {}
    for r in rows:
        stats[r["asset_type"]] = {
            "count": r["cnt"],
            "total_size": r["total_size"] or 0,
        }
    return stats


def _row_to_dict(row) -> dict:
    """将 sqlite3.Row 转换为 dict。"""
    d = dict(row)
    d["source_asset_ids"] = json.loads(d.pop("source_asset_ids", "[]"))
    d["metadata"] = json.loads(d.pop("metadata", "{}"))
    return d


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
