"""Execution event bus — 事件先落库，再推送到订阅者。"""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from backend.app.db.connection import get_connection


@dataclass
class ExecutionEvent:
    event_id: str
    execution_id: str
    node_id: str
    item_key: str | None
    type: str           # node.started / node.progress / node.completed / node.failed / execution.completed
    status: str
    progress: int = 0
    message: str = ""
    timestamp: str = ""


# WebSocket 订阅者列表：execution_id -> [callback]
_subscribers: dict[str, list[Callable[[dict], Awaitable[None]]]] = {}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def emit_event(
    execution_id: str,
    node_id: str,
    event_type: str,
    status: str,
    item_key: str | None = None,
    progress: int = 0,
    message: str = "",
) -> dict:
    """发送事件：先写数据库，再通知订阅者。"""
    import uuid
    conn = get_connection()
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    now = _now_iso()

    conn.execute(
        "INSERT INTO execution_events (id, execution_id, node_id, item_key, type, status, progress, message, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, execution_id, node_id, item_key, event_type, status, progress, message, now),
    )
    conn.commit()

    event_data = {
        "event_id": event_id,
        "execution_id": execution_id,
        "node_id": node_id,
        "item_key": item_key,
        "type": event_type,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": now,
    }

    # 通知订阅者（异步）
    subscribers = _subscribers.get(execution_id, [])
    for cb in subscribers:
        asyncio.get_event_loop().create_task(cb(event_data))

    return event_data


def subscribe(execution_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
    """订阅执行事件。"""
    _subscribers.setdefault(execution_id, []).append(callback)


def unsubscribe(execution_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
    """取消订阅。"""
    if execution_id in _subscribers:
        _subscribers[execution_id] = [cb for cb in _subscribers[execution_id] if cb != callback]


def get_events(execution_id: str, after_event_id: str | None = None) -> list[dict]:
    """获取执行事件（支持按 event_id 补拉）。"""
    conn = get_connection()
    if after_event_id:
        rows = conn.execute(
            "SELECT * FROM execution_events WHERE execution_id = ? "
            "AND timestamp > (SELECT timestamp FROM execution_events WHERE id = ?) "
            "ORDER BY timestamp",
            (execution_id, after_event_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM execution_events WHERE execution_id = ? ORDER BY timestamp",
            (execution_id,),
        ).fetchall()
    return [dict(row) for row in rows]
