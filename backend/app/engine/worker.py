"""Worker — 轮询任务队列，分发给 Handler 执行。"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, Any

from backend.app.engine.queue import claim_task, complete_task, fail_task, heartbeat, recover_orphans
from backend.app.services.event_bus import emit_event

logger = logging.getLogger(__name__)


class NodeHandler(Protocol):
    """节点执行器协议。"""
    async def execute(self, task: dict, context: dict) -> dict: ...


# Handler 注册表
_handlers: dict[str, NodeHandler] = {}


def register_handler(kind: str, handler: NodeHandler) -> None:
    _handlers[kind] = handler


def get_handler(kind: str) -> NodeHandler | None:
    return _handlers.get(kind)


class Worker:
    """异步 Worker，持续轮询任务队列。"""

    def __init__(self, worker_id: str, poll_interval: float = 0.5, lease_seconds: int = 30):
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self.lease_seconds = lease_seconds
        self._running = False
        self._task_count = 0

    async def start(self) -> None:
        """启动 Worker 主循环。"""
        self._running = True
        logger.info(f"Worker {self.worker_id} 启动")
        while self._running:
            try:
                # 回收超时任务
                recover_orphans(self.worker_id, self.lease_seconds)

                # 领取任务
                task = claim_task(self.worker_id, self.lease_seconds)
                if task is None:
                    await asyncio.sleep(self.poll_interval)
                    continue

                await self._execute_task(task)
            except Exception as e:
                logger.error(f"Worker {self.worker_id} 异常: {e}")
                await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        logger.info(f"Worker {self.worker_id} 停止，共执行 {self._task_count} 个任务")

    async def _execute_task(self, task: dict) -> None:
        """执行单个任务。"""
        execution_id = task.get("execution_id", "")
        task_id = task["id"]
        node_id = task.get("node_id", "")
        kind = task.get("kind", "")
        item_key = task.get("item_key")

        handler = get_handler(kind)
        if handler is None:
            logger.warning(f"未找到 {kind} 的 Handler，跳过任务 {task_id}")
            fail_task(task_id, f"无 Handler: {kind}")
            emit_event(execution_id, node_id, "node.failed", "failed",
                       item_key=item_key, message=f"无 Handler: {kind}")
            return

        # 发送开始事件
        emit_event(execution_id, node_id, "node.started", "running",
                   item_key=item_key, message=f"开始执行: {task.get('label', kind)}")

        try:
            # 定期续租
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id))

            # 执行
            result = await handler.execute(task, {"worker_id": self.worker_id})

            heartbeat_task.cancel()
            complete_task(task_id)
            self._task_count += 1

            # 发送完成事件
            emit_event(execution_id, node_id, "node.completed", "completed",
                       item_key=item_key, progress=100,
                       message=f"完成: {task.get('label', kind)}")
        except asyncio.CancelledError:
            heartbeat_task.cancel()
            fail_task(task_id, "任务被取消")
            emit_event(execution_id, node_id, "node.failed", "failed",
                       item_key=item_key, message="任务被取消")
        except Exception as e:
            heartbeat_task.cancel()
            error_msg = str(e)
            fail_task(task_id, error_msg)
            emit_event(execution_id, node_id, "node.failed", "failed",
                       item_key=item_key, message=f"失败: {error_msg}")
            logger.error(f"任务 {task_id} 执行失败: {e}")

    async def _heartbeat_loop(self, task_id: str) -> None:
        """定期续租。"""
        while True:
            await asyncio.sleep(self.lease_seconds // 2)
            heartbeat(task_id, self.lease_seconds)
