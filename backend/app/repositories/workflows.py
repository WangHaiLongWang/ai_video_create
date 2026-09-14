"""Workflow CRUD repository with optimistic locking."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.app.db.connection import get_connection


class OptimisticLockError(Exception):
    """乐观锁版本冲突。"""


class WorkflowNotFoundError(Exception):
    """工作流不存在。"""


def list_workflows() -> list[dict]:
    """返回工作流摘要列表（不含完整 spec）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, description, version, created_at, updated_at "
        "FROM workflows ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get_workflow(workflow_id: str) -> dict:
    """返回完整工作流（含 spec_json 解析后的 spec）。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
    ).fetchone()
    if row is None:
        raise WorkflowNotFoundError(f"工作流 {workflow_id} 不存在")
    result = dict(row)
    result["spec"] = json.loads(result.pop("spec_json"))
    return result


def create_workflow(spec: dict, name: str | None = None, description: str = "") -> dict:
    """创建工作流，返回摘要。"""
    conn = get_connection()
    wf_id = spec.get("id", "")
    wf_name = name or spec.get("name", "未命名工作流")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO workflows (id, name, description, schema_version, spec_json, version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (wf_id, wf_name, description, spec.get("schemaVersion", "1.0"), json.dumps(spec, ensure_ascii=False), now, now),
    )
    conn.commit()
    return {"id": wf_id, "name": wf_name, "version": 1, "created_at": now, "updated_at": now}


def update_workflow(workflow_id: str, spec: dict, expected_version: int) -> dict:
    """乐观锁更新工作流。"""
    conn = get_connection()
    row = conn.execute("SELECT version, name, created_at FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    if row is None:
        raise WorkflowNotFoundError(f"工作流 {workflow_id} 不存在")
    if row["version"] != expected_version:
        raise OptimisticLockError(
            f"版本冲突：期望 v{expected_version}，实际 v{row['version']}"
        )
    now = datetime.now(timezone.utc).isoformat()
    new_version = expected_version + 1
    new_name = spec.get("name", row["name"])
    conn.execute(
        "UPDATE workflows SET spec_json = ?, version = ?, name = ?, updated_at = ? WHERE id = ?",
        (json.dumps(spec, ensure_ascii=False), new_version, new_name, now, workflow_id),
    )
    conn.commit()
    return {"id": workflow_id, "name": new_name, "version": new_version, "created_at": row["created_at"], "updated_at": now}


def delete_workflow(workflow_id: str) -> None:
    """删除工作流。"""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    conn.commit()
    if cursor.rowcount == 0:
        raise WorkflowNotFoundError(f"工作流 {workflow_id} 不存在")


def duplicate_workflow(workflow_id: str, new_name: str | None = None) -> dict:
    """复制工作流，生成新 ID。"""
    import uuid

    original = get_workflow(workflow_id)
    spec = original["spec"]
    new_id = f"wf-{uuid.uuid4().hex[:12]}"
    new_spec = {**spec, "id": new_id}
    name = new_name or f"{original['name']} (副本)"
    return create_workflow(new_spec, name=name, description=original.get("description", ""))
