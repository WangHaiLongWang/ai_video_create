"""Execution REST + WebSocket API."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.app.db.connection import get_connection
from backend.app.engine.compiler import compile_workflow, CompileError
from backend.app.engine.queue import get_tasks_by_execution, enqueue_tasks
from backend.app.engine.worker import Worker, register_handler
from backend.app.services.event_bus import emit_event, subscribe, unsubscribe, get_events
from backend.app.handlers.base import (
    TextInputHandler, StoryboardHandler, TextToImageHandler,
    ImageToVideoHandler, VideoConcatHandler, OutputHandler,
)

# 注册 Mock Handlers
register_handler("textInput", TextInputHandler())
register_handler("storyboard", StoryboardHandler())
register_handler("textToImage", TextToImageHandler())
register_handler("imageToVideo", ImageToVideoHandler())
register_handler("videoConcat", VideoConcatHandler())
register_handler("output", OutputHandler())

router = APIRouter(prefix="/api/executions", tags=["executions"])

# 全局 Worker 实例
_worker: Worker | None = None
_worker_task: asyncio.Task | None = None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def get_worker() -> Worker:
    global _worker
    if _worker is None:
        _worker = Worker(worker_id="worker-main", poll_interval=0.3)
    return _worker


async def start_worker_background() -> None:
    """在 app lifespan 中调用，后台启动 Worker。"""
    global _worker_task
    worker = get_worker()
    _worker_task = asyncio.create_task(worker.start())


async def stop_worker_background() -> None:
    """在 app lifespan 中调用，停止 Worker。"""
    global _worker_task, _worker
    if _worker:
        await _worker.stop()
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker = None
    _worker_task = None


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    task_count: int = 0


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
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
        "VALUES (?, ?, ?, 'running', ?)",
        (execution_id, workflow_id, json.dumps(spec, ensure_ascii=False), now),
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
