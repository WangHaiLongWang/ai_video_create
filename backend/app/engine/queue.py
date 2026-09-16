"""SQLite-based task queue with atomic claim, lease, heartbeat, and retry."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

from backend.app.db.connection import get_connection
from backend.app.engine.retry import (
    RetryPolicy,
    classify_error,
    should_retry,
    calculate_delay,
    get_retry_after,
    get_default_policy,
)
from backend.app.handlers.contracts import NodeError


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
    """原子领取一个可执行任务（依赖全部完成 + 状态为 pending + 退避时间已过）。"""
    conn = get_connection()
    now = _now_iso()
    lease = _lease_until(lease_seconds)

    # 找到一个依赖全部完成的 pending 任务
    # 注意：需跳过 next_retry_at 未到的任务（退避中）
    row = conn.execute(
        "SELECT t.id, t.depends_on_json FROM tasks t "
        "WHERE t.status = 'pending' "
        "AND (t.next_retry_at IS NULL OR t.next_retry_at <= ?) "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM tasks dep "
        "  WHERE dep.id IN (SELECT value FROM json_each(t.depends_on_json)) "
        "  AND dep.status != 'completed'"
        ") "
        "LIMIT 1",
        (now,),
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
    """标记任务完成，仅当任务状态为 running 时更新。"""
    conn = get_connection()
    now = _now_iso()
    result_json = json.dumps(result, ensure_ascii=False) if result else "{}"

    # 条件更新：只更新 running 状态的任务
    cursor = conn.execute(
        "UPDATE tasks SET status = 'completed', completed_at = ?, result_json = ? "
        "WHERE id = ? AND status = 'running'",
        (now, result_json, task_id),
    )
    conn.commit()

    if cursor.rowcount > 0:
        _check_execution_convergence(task_id)


def fail_task(
    task_id: str,
    error: str | NodeError = "",
    max_retries: int = 3,
    policy: RetryPolicy | None = None,
) -> list[str]:
    """标记任务失败，支持智能重试和退避，递归传播到所有下游。

    增强逻辑：
    1. 将 error 参数规范化为 NodeError
    2. 使用 RetryPolicy 分类错误并判断是否可重试
    3. 计算指数退避延迟，设置 next_retry_at
    4. 记录 error_code 到 tasks 表
    5. 不可重试时直接标记为永久失败并传播

    Args:
        task_id: 任务 ID
        error: 错误信息（字符串或 NodeError）
        max_retries: 最大重试次数（向后兼容）
        policy: 重试策略，为 None 时使用默认策略

    Returns:
        被跳过的下游任务 ID 列表
    """
    conn = get_connection()
    now = _now_iso()

    # 将 error 规范化为 NodeError
    if isinstance(error, str):
        node_error = NodeError(code="UNKNOWN", message=error, retryable=False)
    else:
        node_error = error

    # 获取当前任务信息
    row = conn.execute(
        "SELECT attempt FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    attempt = (row["attempt"] if row else 0) + 1

    # 使用 policy 判断是否可重试（向后兼容：如果未传 policy 则用 max_retries 做简单判断）
    if policy is not None:
        retryable = should_retry(node_error, attempt, policy)
    else:
        retryable = attempt < max_retries

    # 分类错误
    category = classify_error(node_error)
    error_code = node_error.code
    error_msg = node_error.message

    # 从 429 等响应中提取 Retry-After
    retry_after = get_retry_after(node_error)

    if retryable:
        # 计算退避延迟
        if policy is not None:
            delay = retry_after if retry_after is not None else calculate_delay(attempt, policy)
            next_retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=delay)
            ).isoformat()
        else:
            # 向后兼容：无 policy 时不设置 next_retry_at，立即重试
            next_retry_at = None

        # 可重试：重置为 pending，增加 attempt，记录退避时间
        if next_retry_at:
            conn.execute(
                "UPDATE tasks SET status = 'pending', error = ?, error_code = ?, attempt = ?, "
                "next_retry_at = ?, worker_id = NULL, lease_until = NULL, started_at = NULL "
                "WHERE id = ?",
                (error_msg, error_code, attempt, next_retry_at, task_id),
            )
        else:
            conn.execute(
                "UPDATE tasks SET status = 'pending', error = ?, error_code = ?, attempt = ?, "
                "worker_id = NULL, lease_until = NULL, started_at = NULL WHERE id = ?",
                (error_msg, error_code, attempt, task_id),
            )
        conn.commit()
        return []

    # 超过重试次数或不可重试，标记失败
    conn.execute(
        "UPDATE tasks SET status = 'failed', error = ?, error_code = ?, attempt = ?, completed_at = ? "
        "WHERE id = ?",
        (error_msg, error_code, attempt, now, task_id),
    )
    conn.commit()

    # 递归传播：找到所有直接或间接依赖此任务的 pending 任务
    skipped = _propagate_failure_recursive(task_id, now)
    return skipped


# ---------------------------------------------------------------------------
# 单节点重试 API 支持
# ---------------------------------------------------------------------------


def retry_node_task(
    execution_id: str,
    node_id: str,
    idempotency_key: str | None = None,
) -> dict:
    """重试单个失败节点。

    流程：
    1. 查找指定 execution 中状态为 failed 的对应 node_id 的任务
    2. 检查幂等键防止重复重试
    3. 重置任务状态为 pending，清除退避信息
    4. 返回重置后的任务信息

    Args:
        execution_id: 执行 ID
        node_id: 要重试的节点 ID
        idempotency_key: 幂等键，防止重复重试

    Returns:
        重置后的任务字典

    Raises:
        ValueError: 节点不存在或状态不是 failed
        DuplicateRetryError: 幂等键冲突
    """
    conn = get_connection()
    now = _now_iso()

    # 1. 检查幂等键 — 防止对同一任务的重复重试请求
    if idempotency_key:
        # 查找使用此幂等键的非 failed 任务（说明之前已经重试过且正在执行/已完成）
        existing = conn.execute(
            "SELECT id, status FROM tasks "
            "WHERE execution_id = ? AND idempotency_key = ? AND status != 'failed'",
            (execution_id, idempotency_key),
        ).fetchone()
        if existing:
            raise DuplicateRetryError(
                f"幂等键 {idempotency_key} 已被使用，任务 {existing['id']} 状态为 {existing['status']}"
            )

    # 2. 查找 failed 状态的任务
    row = conn.execute(
        "SELECT * FROM tasks WHERE execution_id = ? AND node_id = ? AND status = 'failed'",
        (execution_id, node_id),
    ).fetchone()

    if row is None:
        raise ValueError(
            f"节点 {node_id} 在执行 {execution_id} 中不存在或状态不是 failed"
        )

    task_id = row["id"]

    # 3. 重置任务为 pending，清除退避和错误信息
    conn.execute(
        "UPDATE tasks SET status = 'pending', error = '', error_code = NULL, "
        "attempt = 0, next_retry_at = NULL, "
        "worker_id = NULL, lease_until = NULL, "
        "started_at = NULL, completed_at = NULL, "
        "idempotency_key = ? "
        "WHERE id = ?",
        (idempotency_key, task_id),
    )
    conn.commit()

    # 4. 返回更新后的任务
    return _get_task_raw(task_id)


def check_idempotency(execution_id: str, idempotency_key: str) -> dict | None:
    """检查幂等键是否已存在。

    Args:
        execution_id: 执行 ID
        idempotency_key: 幂等键

    Returns:
        已存在的任务字典，不存在时返回 None
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tasks WHERE execution_id = ? AND idempotency_key = ?",
        (execution_id, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    return _get_task_raw(row["id"])


def _get_task_raw(task_id: str) -> dict:
    """获取任务原始数据（不做 JSON 反序列化）。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise TaskNotFoundError(f"任务 {task_id} 不存在")
    return dict(row)


def get_retryable_tasks(execution_id: str) -> list[dict]:
    """获取可重试的任务（failed 状态）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE execution_id = ? AND status = 'failed' "
        "ORDER BY task_index, id",
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


class DuplicateRetryError(Exception):
    """幂等键冲突错误。"""
    pass


def _propagate_failure_recursive(failed_task_id: str, now: str) -> list[str]:
    """递归传播失败到所有下游任务。"""
    conn = get_connection()

    # 使用 CTE 递归查找所有依赖链
    query = """
    WITH RECURSIVE dependents AS (
        -- 基础：直接依赖 failed_task_id 的任务
        SELECT t.id, t.depends_on_json
        FROM tasks t
        WHERE EXISTS (
            SELECT 1 FROM json_each(t.depends_on_json)
            WHERE value = ?
        )
        AND t.status = 'pending'

        UNION ALL

        -- 递归：依赖 dependents 的任务
        SELECT t.id, t.depends_on_json
        FROM tasks t
        INNER JOIN dependents d ON EXISTS (
            SELECT 1 FROM json_each(t.depends_on_json)
            WHERE value = d.id
        )
        WHERE t.status = 'pending'
    )
    SELECT id FROM dependents
    """

    rows = conn.execute(query, (failed_task_id,)).fetchall()
    if rows:
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE tasks SET status = 'skipped', completed_at = ? WHERE id IN ({placeholders})",
            [now] + ids,
        )
        conn.commit()
        return ids

    return []


def cancel_task(task_id: str) -> list[str]:
    """取消任务，递归取消所有下游 pending 任务。"""
    conn = get_connection()
    now = _now_iso()

    # 取消当前任务（仅 pending 或 running）
    cursor = conn.execute(
        "UPDATE tasks SET status = 'cancelled', completed_at = ? "
        "WHERE id = ? AND status IN ('pending', 'running')",
        (now, task_id),
    )
    conn.commit()

    if cursor.rowcount == 0:
        return []

    # 递归取消下游
    cancelled = _propagate_cancel_recursive(task_id, now)
    return cancelled


def _propagate_cancel_recursive(cancelled_task_id: str, now: str) -> list[str]:
    """递归取消所有依赖此任务的 pending 任务。"""
    conn = get_connection()

    query = """
    WITH RECURSIVE dependents AS (
        SELECT t.id
        FROM tasks t
        WHERE EXISTS (
            SELECT 1 FROM json_each(t.depends_on_json)
            WHERE value = ?
        )
        AND t.status = 'pending'

        UNION ALL

        SELECT t.id
        FROM tasks t
        INNER JOIN dependents d ON EXISTS (
            SELECT 1 FROM json_each(t.depends_on_json)
            WHERE value = d.id
        )
        WHERE t.status = 'pending'
    )
    SELECT id FROM dependents
    """

    rows = conn.execute(query, (cancelled_task_id,)).fetchall()
    if rows:
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE tasks SET status = 'cancelled', completed_at = ? WHERE id IN ({placeholders})",
            [now] + ids,
        )
        conn.commit()

    return [r["id"] for r in rows]


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


def save_external_job_id(task_id: str, external_job_id: str) -> None:
    """持久化外部任务 ID（如 Wan3 API 返回的 task_id）到 tasks 表。"""
    conn = get_connection()
    conn.execute(
        "UPDATE tasks SET external_job_id = ? WHERE id = ?",
        (external_job_id, task_id),
    )
    conn.commit()


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
