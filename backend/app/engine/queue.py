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


def complete_task(task_id: str, result: dict | None = None) -> None:
    """标记任务完成，可选持久化结果。"""
    conn = get_connection()
    now = _now_iso()
    result_json = json.dumps(result, ensure_ascii=False) if result else "{}"
    conn.execute(
        "UPDATE tasks SET status = 'completed', completed_at = ?, result_json = ? WHERE id = ?",
        (now, result_json, task_id),
    )
    conn.commit()
    # 检查执行是否所有任务完成
    _check_execution_convergence(task_id)


def fail_task(task_id: str, error: str = "", max_retries: int = 3) -> list[str]:
    """标记任务失败，支持重试，传播到下游。"""
    conn = get_connection()
    now = _now_iso()

    # 获取当前任务的重试次数
    row = conn.execute(
        "SELECT attempt FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    attempt = (row["attempt"] if row else 0) + 1

    if attempt < max_retries:
        # 可重试：重置为 pending，增加 attempt 计数
        conn.execute(
            "UPDATE tasks SET status = 'pending', error = ?, attempt = ?, "
            "worker_id = NULL, lease_until = NULL, started_at = NULL WHERE id = ?",
            (error, attempt, task_id),
        )
        conn.commit()
        return []
    else:
        # 超过最大重试次数：标记为失败，传播到下游
        conn.execute(
            "UPDATE tasks SET status = 'failed', error = ?, attempt = ?, completed_at = ? WHERE id = ?",
            (error, attempt, now, task_id),
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
    result["result"] = json.loads(result.pop("result_json", "{}"))
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
        r["result"] = json.loads(r.pop("result_json", "{}"))
        results.append(r)
    return results


def get_upstream_results(execution_id: str, depends_on: list[str]) -> dict[str, dict]:
    """获取上游任务的结果。"""
    conn = get_connection()
    if not depends_on:
        return {}
    placeholders = ",".join("?" * len(depends_on))
    rows = conn.execute(
        f"SELECT id, result_json FROM tasks WHERE execution_id = ? AND id IN ({placeholders})",
        [execution_id] + depends_on,
    ).fetchall()
    return {row["id"]: json.loads(row["result_json"]) for row in rows}


def _check_execution_convergence(task_id: str) -> None:
    """检查执行是否所有任务完成，更新执行状态。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT execution_id FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        return
    execution_id = row["execution_id"]

    # 统计任务状态
    stats = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM tasks WHERE execution_id = ? GROUP BY status",
        (execution_id,),
    ).fetchall()
    status_counts = {r["status"]: r["cnt"] for r in stats}
    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    skipped = status_counts.get("skipped", 0)
    cancelled = status_counts.get("cancelled", 0)

    # 更新 executions 表
    now = _now_iso()
    if completed + failed + skipped + cancelled >= total:
        # 所有任务已结束
        if failed > 0 or skipped > 0:
            new_status = "failed"
        elif cancelled > 0:
            new_status = "cancelled"
        else:
            new_status = "completed"
        conn.execute(
            "UPDATE executions SET status = ?, completed_at = ?, completed_count = ? "
            "WHERE id = ?",
            (new_status, now, completed, execution_id),
        )
        conn.commit()
        # 发送执行完成事件
        from backend.app.services.event_bus import emit_event
        emit_event(
            execution_id, "", f"execution.{new_status}", new_status,
            message=f"执行{new_status}: {completed}/{total} 任务完成"
        )
    else:
        # 仅更新完成计数
        conn.execute(
            "UPDATE executions SET completed_count = ? WHERE id = ?",
            (completed, execution_id),
        )
        conn.commit()
