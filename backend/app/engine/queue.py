"""SQLite-based task queue with atomic claim, lease, and heartbeat."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

from backend.app.db.connection import get_connection


class TaskNotFoundError(Exception):
    pass


class LeaseExpiredError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lease_until(seconds: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# --- Queue Operations ---


def enqueue_tasks(workflow_id: str, execution_id: str, tasks: list[dict]) -> None:
    """批量入队任务。tasks: [{id, node_id, kind, label, item_key, index, config, depends_on}]"""
    conn = get_connection()
    now = _now_iso()
    conn.executemany(
        "INSERT INTO tasks (id, workflow_id, execution_id, node_id, kind, label, item_key, "
        "task_index, config_json, depends_on_json, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
        [
            (
                t["id"], workflow_id, execution_id,
                t.get("node_id", ""), t.get("kind", ""), t.get("label", ""),
                t.get("item_key"), t.get("index", 0),
                json.dumps(t.get("config", {}), ensure_ascii=False),
                json.dumps(t.get("depends_on", []), ensure_ascii=False),
                now,
            )
            for t in tasks
        ],
    )
    conn.commit()


def claim_task(worker_id: str, lease_seconds: int = 30) -> dict | None:
    """原子领取一个可执行任务（依赖全部完成 + 状态为 pending）。"""
    conn = get_connection()
    now = _now_iso()
    lease = _lease_until(lease_seconds)

    # 找到一个依赖全部完成的 pending 任务
    row = conn.execute(
        "SELECT t.id, t.depends_on_json FROM tasks t "
        "WHERE t.status = 'pending' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM tasks dep "
        "  WHERE dep.id IN (SELECT value FROM json_each(t.depends_on_json)) "
        "  AND dep.status != 'completed'"
        ") "
        "LIMIT 1"
    ).fetchone()

    if row is None:
        return None

    task_id = row["id"]

    # BEGIN IMMEDIATE 保证原子性
    conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = conn.execute(
            "UPDATE tasks SET status = 'running', worker_id = ?, lease_until = ?, started_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (worker_id, lease, now, task_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            conn.execute("ROLLBACK")
            return None
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return get_task(task_id)


def heartbeat(task_id: str, lease_seconds: int = 30) -> None:
    """续租任务。"""
    conn = get_connection()
    lease = _lease_until(lease_seconds)
    conn.execute(
        "UPDATE tasks SET lease_until = ? WHERE id = ? AND status = 'running'",
        (lease, task_id),
    )
    conn.commit()


def complete_task(task_id: str) -> None:
    """标记任务完成。"""
    conn = get_connection()
    now = _now_iso()
    conn.execute(
        "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
        (now, task_id),
    )
    conn.commit()


def fail_task(task_id: str, error: str = "") -> list[str]:
    """标记任务失败，传播到下游。"""
    conn = get_connection()
    now = _now_iso()
    conn.execute(
        "UPDATE tasks SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
        (error, now, task_id),
    )
    # 传播：所有依赖此任务的 pending 任务标记为 skipped
    cursor = conn.execute(
        "UPDATE tasks SET status = 'skipped', completed_at = ? "
        "WHERE status = 'pending' AND id IN ("
        "  SELECT t.id FROM tasks t "
        "  WHERE EXISTS (SELECT 1 FROM json_each(t.depends_on_json) WHERE value = ?)"
        ")",
        (now, task_id),
    )
    conn.commit()
    # 返回被跳过的任务 ids
    skipped = conn.execute(
        "SELECT id FROM tasks WHERE status = 'skipped' AND completed_at = ?",
        (now,),
    ).fetchall()
    return [r["id"] for r in skipped]


def cancel_task(task_id: str) -> None:
    """取消任务。"""
    conn = get_connection()
    now = _now_iso()
    conn.execute(
        "UPDATE tasks SET status = 'cancelled', completed_at = ? WHERE id = ? AND status IN ('pending', 'running')",
        (now, task_id),
    )
    conn.commit()


def recover_orphans(worker_id: str, lease_seconds: int = 30) -> list[str]:
    """回收超时的 running 任务（租约过期）。"""
    conn = get_connection()
    now = _now_iso()
    cursor = conn.execute(
        "UPDATE tasks SET status = 'pending', worker_id = NULL, lease_until = NULL "
        "WHERE status = 'running' AND lease_until < ?",
        (now,),
    )
    conn.commit()
    if cursor.rowcount > 0:
        orphans = conn.execute(
            "SELECT id FROM tasks WHERE status = 'pending' AND worker_id IS NULL "
            "AND lease_until IS NULL"
        ).fetchall()
        return [r["id"] for r in orphans[:cursor.rowcount]]
    return []


def get_task(task_id: str) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskNotFoundError(f"任务 {task_id} 不存在")
    result = dict(row)
    result["config"] = json.loads(result.pop("config_json", "{}"))
    result["depends_on"] = json.loads(result.pop("depends_on_json", "[]"))
    return result


def get_tasks_by_execution(execution_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE execution_id = ? ORDER BY task_index, id",
        (execution_id,),
    ).fetchall()
    results = []
    for row in rows:
        r = dict(row)
        r["config"] = json.loads(r.pop("config_json", "{}"))
        r["depends_on"] = json.loads(r.pop("depends_on_json", "[]"))
        results.append(r)
    return results
