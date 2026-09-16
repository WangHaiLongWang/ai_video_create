"""Execution REST + WebSocket API."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.app.db.connection import get_connection
from backend.app.engine.compiler import compile_workflow, CompileError
from backend.app.engine.queue import (
    get_tasks_by_execution,
    enqueue_tasks,
    retry_node_task,
    DuplicateRetryError,
)
from backend.app.engine.worker import WorkerPool
from backend.app.services.event_bus import emit_event, subscribe, unsubscribe, get_events
from backend.app.handlers import get_handler

router = APIRouter(prefix="/api/executions", tags=["executions"])

# 全局 Worker 池实例（由 main.py lifespan 管理）
_worker_pool: WorkerPool | None = None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def start_worker_background() -> None:
    """在 app lifespan 中调用，后台启动 Worker 池。"""
    global _worker_pool
    from backend.app.config import get_settings
    settings = get_settings()
    _worker_pool = WorkerPool(
        worker_count=settings.WORKER_COUNT,
        poll_interval=settings.WORKER_POLL_INTERVAL,
        lease_seconds=settings.WORKER_LEASE_SECONDS,
    )
    await _worker_pool.start()


async def stop_worker_background() -> None:
    """在 app lifespan 中调用，停止 Worker 池。"""
    global _worker_pool
    if _worker_pool:
        await _worker_pool.stop()
        _worker_pool = None


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    task_count: int = 0


class RetryNodeRequest(BaseModel):
    """单节点重试请求。"""
    node_id: str = Field(..., description="要重试的节点 ID")
    idempotency_key: str | None = Field(None, description="幂等键，防止重复重试")


@router.post("/{workflow_id}/start", response_model=ExecutionResponse, status_code=201)
def start_execution(workflow_id: str) -> dict:
    """启动一次执行。"""
    conn = get_connection()

    # 读取工作流
    wf_row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    if wf_row is None:
        raise HTTPException(status_code=404, detail=f"工作流 {workflow_id} 不存在")

    spec = json.loads(wf_row["spec_json"])

    # 编译
    try:
        plan = compile_workflow(spec)
    except CompileError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 创建执行记录
    execution_id = f"exec-{uuid.uuid4().hex[:12]}"
    now = _now_iso()
    task_count = len(plan.tasks)
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, task_count, created_at) "
        "VALUES (?, ?, ?, 'running', ?, ?)",
        (execution_id, workflow_id, json.dumps(spec, ensure_ascii=False), task_count, now),
    )
    conn.commit()

    # 入队所有任务
    task_dicts = [
        {
            "id": t.id,
            "node_id": t.node_id,
            "kind": t.node_kind,
            "label": t.node_label,
            "item_key": t.item_key,
            "index": t.index,
            "config": t.config,
            "depends_on": t.depends_on,
        }
        for t in plan.tasks
    ]
    enqueue_tasks(workflow_id, execution_id, task_dicts)

    # 发送执行开始事件
    emit_event(execution_id, "", "execution.started", "running",
               message=f"执行开始: {plan.workflow_name}, {len(plan.tasks)} 个任务")

    return {
        "id": execution_id,
        "workflow_id": workflow_id,
        "status": "running",
        "task_count": len(plan.tasks),
    }


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: str) -> dict:
    """获取执行状态。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"执行 {execution_id} 不存在")

    tasks = get_tasks_by_execution(execution_id)
    task_summary = {}
    for t in tasks:
        s = t["status"]
        task_summary[s] = task_summary.get(s, 0) + 1

    return {
        "id": row["id"],
        "workflow_id": row["workflow_id"],
        "status": row["status"],
        "task_count": len(tasks),
        "task_summary": task_summary,
    }


@router.get("/{execution_id}/tasks")
def get_execution_tasks(execution_id: str) -> list[dict]:
    """获取执行的所有任务。"""
    return get_tasks_by_execution(execution_id)


@router.get("/{execution_id}/events")
def get_execution_events(execution_id: str, after: str | None = None) -> list[dict]:
    """获取执行事件（支持按 event_id 补拉）。"""
    return get_events(execution_id, after_event_id=after)


@router.post("/{execution_id}/cancel")
def cancel_execution(execution_id: str) -> dict:
    """取消执行。"""
    conn = get_connection()
    conn.execute(
        "UPDATE executions SET status = 'cancelled' WHERE id = ? AND status IN ('pending', 'running')",
        (execution_id,),
    )
    conn.execute(
        "UPDATE tasks SET status = 'cancelled' WHERE execution_id = ? AND status IN ('pending', 'running')",
        (execution_id,),
    )
    conn.commit()
    emit_event(execution_id, "", "execution.cancelled", "cancelled", message="执行已取消")
    return {"id": execution_id, "status": "cancelled"}


@router.post("/{execution_id}/retry")
def retry_node(execution_id: str, request: RetryNodeRequest) -> dict:
    """重试失败的单个节点。

    流程：
    1. 验证执行记录存在
    2. 验证节点状态为 failed
    3. 检查幂等键防止重复
    4. 重置任务状态为 pending
    5. 发送节点重试事件

    Returns:
        包含重试任务信息的字典
    """
    # 验证执行记录存在
    conn = get_connection()
    exec_row = conn.execute(
        "SELECT id, status FROM executions WHERE id = ?", (execution_id,)
    ).fetchone()
    if exec_row is None:
        raise HTTPException(status_code=404, detail=f"执行 {execution_id} 不存在")

    try:
        task = retry_node_task(
            execution_id=execution_id,
            node_id=request.node_id,
            idempotency_key=request.idempotency_key,
        )
    except DuplicateRetryError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 发送重试事件
    item_key = task.get("item_key")
    emit_event(
        execution_id,
        request.node_id,
        "node.retrying",
        "pending",
        item_key=item_key,
        message=f"节点 {request.node_id} 已重置为待重试",
    )

    return {
        "execution_id": execution_id,
        "task_id": task["id"],
        "node_id": request.node_id,
        "status": "pending",
        "idempotency_key": request.idempotency_key,
        "message": f"节点 {request.node_id} 已重置为待执行，等待 Worker 调度",
    }


# --- WebSocket ---


@router.websocket("/{execution_id}/ws")
async def execution_ws(websocket: WebSocket, execution_id: str) -> None:
    """WebSocket 实时推送执行事件。"""
    await websocket.accept()

    # 先发送已有的事件快照
    existing = get_events(execution_id)
    for event in existing:
        await websocket.send_json(event)

    # 订阅新事件
    async def push_event(event_data: dict) -> None:
        try:
            await websocket.send_json(event_data)
        except Exception:
            pass

    subscribe(execution_id, push_event)
    try:
        while True:
            # 保持连接，接收客户端消息（如 last_event_id 补拉）
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "replay":
                    after = msg.get("last_event_id")
                    events = get_events(execution_id, after_event_id=after)
                    for event in events:
                        await websocket.send_json(event)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(execution_id, push_event)
