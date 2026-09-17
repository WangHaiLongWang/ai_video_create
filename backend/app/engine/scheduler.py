"""Scheduler — 执行引擎的核心调度器。

职责：
1. 接收 execution_id，从 DB 读取 workflow spec 和所有 tasks
2. 按拓扑序调度 tasks（使用 compiler.py 的拓扑排序结果）
3. 组装 NodeInput：聚合上游 output / map 展开 scene 映射
4. 调用 Worker 执行 tasks
5. 监控 execution 终态（所有 tasks 完成/失败/取消时收敛）
6. 处理重试逻辑
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.db.connection import get_connection
from backend.app.engine.compiler import (
    compile_workflow,
    _extract_scenes,
)
from backend.app.engine.queue import (
    enqueue_tasks,
    get_tasks_by_execution,
    get_upstream_results,
    complete_task as queue_complete,
    fail_task as queue_fail,
    cancel_task as queue_cancel,
)
from backend.app.engine.worker import WorkerPool
from backend.app.handlers.contracts import NodeResult, NodeError
from backend.app.services.event_bus import emit_event

logger = logging.getLogger(__name__)


class SchedulerError(Exception):
    """调度器错误。"""


class Scheduler:
    """核心调度器：编排 execution 生命周期，管理任务调度与状态流转。

    通过与 WorkerPool、queue.py、compiler.py 的集成，完成从工作流编译到
    执行收敛的全流程管理。

    Attributes:
        worker_pool: 可选的 WorkerPool 实例。如果提供，任务将由 Worker 异步
            轮询执行；如果不提供，仅做状态管理和调度（适用于测试）。
        max_retries: 任务失败后的最大重试次数。
        poll_interval: 当等待上游任务完成时的轮询间隔（秒）。
    """

    def __init__(
        self,
        worker_pool: WorkerPool | None = None,
        max_retries: int = 3,
        poll_interval: float = 0.5,
    ) -> None:
        self.worker_pool = worker_pool
        self.max_retries = max_retries
        self.poll_interval = poll_interval

    # ------------------------------------------------------------------
    #  公开接口
    # ------------------------------------------------------------------

    async def start_execution(self, execution_id: str) -> list[str]:
        """启动一个 execution：编译工作流、入队任务、触发首批调度。

        Args:
            execution_id: 执行记录 ID。

        Returns:
            首批可执行的 task_id 列表。

        Raises:
            SchedulerError: execution 不存在或 workflow spec 无效。
        """
        conn = get_connection()

        # 1. 读取 execution 记录
        row = conn.execute(
            "SELECT id, workflow_id, workflow_snapshot, status "
            "FROM executions WHERE id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise SchedulerError(f"Execution {execution_id} 不存在")
        if row["status"] not in ("pending", "running"):
            raise SchedulerError(
                f"Execution {execution_id} 状态为 {row['status']}，无法启动"
            )

        execution_id_val = row["id"]
        workflow_id = row["workflow_id"]

        # 2. 解析 workflow spec（优先使用 workflow_snapshot）
        spec_str = row["workflow_snapshot"]
        spec: dict = {}
        if spec_str and spec_str != "{}":
            try:
                spec = json.loads(spec_str)
            except json.JSONDecodeError:
                pass

        # 如果 snapshot 为空，从 workflows 表读取
        if not spec or not spec.get("nodes"):
            wf_row = conn.execute(
                "SELECT spec_json FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if wf_row:
                try:
                    spec = json.loads(wf_row["spec_json"])
                except json.JSONDecodeError:
                    spec = {}

        if not spec or not spec.get("nodes"):
            raise SchedulerError(
                f"Workflow {workflow_id} 的 spec 为空或无节点"
            )

        # 确保 spec 包含 id
        spec.setdefault("id", workflow_id)

        # 3. 编译工作流
        plan = compile_workflow(spec)

        # 4. 更新 execution 状态为 running
        conn.execute(
            "UPDATE executions SET status = 'running', started_at = datetime('now') "
            "WHERE id = ? AND status = 'pending'",
            (execution_id_val,),
        )
        conn.commit()

        # 5. 入队所有 tasks
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
        enqueue_tasks(workflow_id, execution_id_val, task_dicts)

        logger.info(
            f"Execution {execution_id_val} 已启动，共 {len(plan.tasks)} 个任务"
        )

        # 6. 触发首批可执行任务
        ready_ids = await self.schedule_next_tasks(execution_id_val)

        # 7. 如果有 WorkerPool，确保它在运行
        # （WorkerPool 会自行轮询 claim_task，不需要额外操作）

        return ready_ids

    async def schedule_next_tasks(self, execution_id: str) -> list[str]:
        """查找并返回当前可执行的 task_ids（依赖全部完成、状态为 pending）。

        Args:
            execution_id: 执行记录 ID。

        Returns:
            可执行的 task_id 列表。
        """
        tasks = get_tasks_by_execution(execution_id)
        ready_ids: list[str] = []

        for task in tasks:
            if task["status"] != "pending":
                continue
            # 检查所有依赖是否已完成
            deps = task.get("depends_on", [])
            if not deps:
                ready_ids.append(task["id"])
                continue

            all_done = True
            for dep_id in deps:
                dep_task = next(
                    (t for t in tasks if t["id"] == dep_id), None
                )
                if dep_task is None or dep_task["status"] != "completed":
                    all_done = False
                    break

            if all_done:
                ready_ids.append(task["id"])

        logger.debug(
            f"Execution {execution_id}: {len(ready_ids)} 个任务可执行"
        )
        return ready_ids

    async def complete_task(self, task_id: str, result: NodeResult) -> None:
        """标记任务完成，更新 execution 计数，并触发下游任务调度。

        支持手动执行模式：如果任务处于 pending 状态（未经过 Worker claim），
        直接将其标记为 completed，确保状态机正确流转。

        Args:
            task_id: 完成的任务 ID。
            result: 任务执行结果。
        """
        from datetime import datetime, timezone

        # 1. 获取任务信息
        conn = get_connection()
        row = conn.execute(
            "SELECT execution_id, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            logger.warning(f"complete_task: 任务 {task_id} 不存在")
            return

        execution_id = row["execution_id"]
        task_status = row["status"]
        result_dict = result.to_dict()

        # 2. 根据当前状态决定如何更新
        now = datetime.now(timezone.utc).isoformat()
        if task_status == "pending":
            # 手动执行模式：直接标记为 completed
            conn.execute(
                "UPDATE tasks SET status = 'completed', completed_at = ?, "
                "result_json = ? WHERE id = ? AND status = 'pending'",
                (now, json.dumps(result_dict, ensure_ascii=False), task_id),
            )
            conn.commit()
        elif task_status == "running":
            # Worker 执行模式：通过 queue 标记完成
            queue_complete(task_id, result_dict)
        else:
            # 已处于终态，不覆盖
            logger.debug(f"complete_task: 任务 {task_id} 已处于 {task_status}，跳过")
            return

        logger.info(f"任务 {task_id} 已完成")

        # 3. 尝试调度下游任务
        await self.schedule_next_tasks(execution_id)

        # 4. 检查收敛
        if self.check_convergence(execution_id):
            logger.info(f"Execution {execution_id} 已收敛")

    async def fail_task(self, task_id: str, error: NodeError) -> None:
        """标记任务失败。支持重试和失败传播。

        支持手动执行模式：如果任务处于 pending 状态，直接处理失败逻辑。

        Args:
            task_id: 失败的任务 ID。
            error: 错误信息。
        """
        conn = get_connection()
        row = conn.execute(
            "SELECT execution_id, status FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            logger.warning(f"fail_task: 任务 {task_id} 不存在")
            return

        execution_id = row["execution_id"]
        task_status = row["status"]

        if task_status in ("completed", "failed", "skipped", "cancelled"):
            # 已处于终态，不覆盖
            return

        # 调用 queue 的 fail_task（内部处理重试和传播，适用于 pending/running 状态）
        skipped = queue_fail(task_id, error.message, self.max_retries)

        if skipped:
            logger.info(
                f"任务 {task_id} 超过重试上限，已传播到 {len(skipped)} 个下游任务"
            )
        else:
            # 可能正在重试（状态回到 pending）
            current = conn.execute(
                "SELECT status, attempt FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if current and current["status"] == "pending":
                logger.info(
                    f"任务 {task_id} 将重试（第 {current['attempt']} 次）"
                )

        # 检查收敛
        if self.check_convergence(execution_id):
            logger.info(f"Execution {execution_id} 已收敛")

    async def cancel_execution(self, execution_id: str) -> None:
        """取消整个 execution：将所有 pending/running 任务标记为 cancelled。

        Args:
            execution_id: 要取消的执行 ID。
        """
        conn = get_connection()
        now = _now_iso()

        # 如果 execution 已处于终态，不重复取消
        exec_row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", (execution_id,)
        ).fetchone()
        if exec_row and exec_row["status"] in ("completed", "failed", "cancelled"):
            return

        # 取消所有 pending/running 的任务
        cursor = conn.execute(
            "UPDATE tasks SET status = 'cancelled', completed_at = ? "
            "WHERE execution_id = ? AND status IN ('pending', 'running')",
            (now, execution_id),
        )
        cancelled_count = cursor.rowcount

        # 更新 execution 状态
        conn.execute(
            "UPDATE executions SET status = 'cancelled', completed_at = ? "
            "WHERE id = ?",
            (now, execution_id),
        )
        conn.commit()

        emit_event(
            execution_id, "", "execution.cancelled", "cancelled",
            message=f"执行已取消：{cancelled_count} 个任务被取消",
        )

        logger.info(
            f"Execution {execution_id} 已取消，{cancelled_count} 个任务被取消"
        )

    def check_convergence(self, execution_id: str) -> bool:
        """检查 execution 是否已收敛（所有 task 处于终态）。

        终态包括：completed / failed / skipped / cancelled。

        Args:
            execution_id: 执行记录 ID。

        Returns:
            True 表示所有任务已达终态。
        """
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) as total FROM tasks WHERE execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None or row["total"] == 0:
            return False

        total = row["total"]

        # 统计非终态任务数
        active = conn.execute(
            "SELECT COUNT(*) as cnt FROM tasks "
            "WHERE execution_id = ? AND status IN ('pending', 'running')",
            (execution_id,),
        ).fetchone()

        is_converged = active["cnt"] == 0 if active else True

        if is_converged:
            self._finalize_execution(execution_id)

        return is_converged

    # ------------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------------

    def get_execution_summary(self, execution_id: str) -> dict:
        """获取 execution 的任务状态摘要。

        Args:
            execution_id: 执行记录 ID。

        Returns:
            包含 total 和各状态计数的字典。
        """
        conn = get_connection()
        stats = conn.execute(
            "SELECT status, COUNT(*) as cnt "
            "FROM tasks WHERE execution_id = ? GROUP BY status",
            (execution_id,),
        ).fetchall()
        result = {r["status"]: r["cnt"] for r in stats}
        result["total"] = sum(result.values())
        return result

    def get_task_results(self, execution_id: str) -> dict[str, dict]:
        """获取 execution 下所有任务的结果。

        Args:
            execution_id: 执行记录 ID。

        Returns:
            task_id -> result dict 映射。
        """
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, result_json, status FROM tasks "
            "WHERE execution_id = ? ORDER BY task_index, id",
            (execution_id,),
        ).fetchall()
        results = {}
        for row in rows:
            result_data = json.loads(row["result_json"]) if row["result_json"] else {}
            results[row["id"]] = {
                "status": row["status"],
                "result": result_data,
            }
        return results

    def assemble_node_input(
        self,
        task: dict,
        execution_id: str,
        tasks: list[dict] | None = None,
    ) -> dict:
        """为指定 task 组装 NodeInput：聚合上游结果，处理 map 展开的 scene 映射。

        对于 map 展开任务（item_key 以 "scene-" 开头），从上游 storyboard
        结果中提取对应 scene 数据并注入到 task config。

        对于 aggregate 任务（如 videoConcat），收集所有上游视频路径并注入
        到 task config["video_paths"]。

        对于普通任务，将所有上游 output 传递为 context。

        Args:
            task: 任务描述字典。
            execution_id: 执行记录 ID。
            tasks: 可选的全量任务列表（避免重复查询）。

        Returns:
            更新后的 task 字典。
        """
        depends_on = task.get("depends_on", [])
        if not depends_on:
            return task

        upstream = get_upstream_results(execution_id, depends_on)

        # Aggregate tasks (videoConcat, etc.): collect upstream video paths
        kind = task.get("kind", "")
        if kind == "videoConcat":
            video_paths = []
            for result in upstream.values():
                if not isinstance(result, dict):
                    continue
                output = result.get("output", result) if isinstance(result, dict) else {}
                if not isinstance(output, dict):
                    continue
                path = str(output.get("path", ""))
                if not path:
                    meta = output.get("metadata", {})
                    if isinstance(meta, dict):
                        path = str(meta.get("path", ""))
                if path:
                    video_paths.append(path)
            # Sort by scene_index + variant_index if available
            # (variant-01 before variant-02 for the same scene)
            config = task.setdefault("config", {})
            config["video_paths"] = video_paths
            return task

        scene_id = task.get("item_key", "")
        if scene_id and scene_id.startswith("scene-"):
            # 解析 scene_id 和 variant_id（支持 "scene-001::variant-01" 格式）
            actual_scene_id = scene_id
            variant_id = ""
            if "::" in scene_id:
                actual_scene_id, variant_id = scene_id.split("::", 1)

            # map 展开任务：注入对应 scene 的数据
            scenes = _extract_scenes(upstream)

            # Extract global style from upstream metadata
            global_style = ""
            global_neg = ""
            for result in upstream.values():
                if isinstance(result, dict):
                    meta = result.get("metadata", result.get("output", {}).get("metadata", {}))
                    if isinstance(meta, dict):
                        global_style = meta.get("globalStyle", global_style)
                        global_neg = meta.get("globalNegativePrompt", global_neg)

            for scene_data in scenes:
                if scene_data.get("scene_id") == actual_scene_id:
                    config = task.setdefault("config", {})
                    config["image_prompt"] = scene_data.get("image_prompt", "")
                    config["video_prompt"] = scene_data.get("video_prompt", "")
                    config["duration"] = scene_data.get(
                        "duration_seconds",
                        scene_data.get("duration", 5.0),
                    )
                    config["metadata"] = scene_data.get("metadata", {})
                    # Pass scene-level negative_prompt to downstream tasks
                    scene_neg = scene_data.get("negative_prompt", "")
                    if scene_neg:
                        config["negative_prompt"] = scene_neg
                    # Pass global style/negative from storyboard metadata
                    if global_style:
                        config["globalStyle"] = global_style
                    if global_neg:
                        config["globalNegativePrompt"] = global_neg
                    if variant_id:
                        config["variant_id"] = variant_id
                    break

        return task

    def aggregate_upstream_outputs(
        self,
        task: dict,
        execution_id: str,
        sort_by_scene_index: bool = False,
    ) -> list[dict]:
        """聚合上游任务的输出，支持按 scene.index 排序。

        用于 videoConcat 等需要按场景顺序合并的 aggregate 任务。

        Args:
            task: 当前任务描述字典。
            execution_id: 执行记录 ID。
            sort_by_scene_index: 是否按 scene index 排序。

        Returns:
            排序后的上游输出列表。
        """
        depends_on = task.get("depends_on", [])
        upstream = get_upstream_results(execution_id, depends_on)

        outputs = list(upstream.values())

        if sort_by_scene_index:
            # 按 scene_index + variant_index 排序
            def _get_sort_key(item: dict) -> tuple[int, int]:
                if not isinstance(item, dict):
                    return (0, 0)
                output = item.get("output", {})
                if isinstance(output, dict):
                    meta = output.get("metadata", {})
                    if isinstance(meta, dict):
                        scene_idx = meta.get("scene_index", meta.get("index", 0))
                        variant_idx = meta.get("variant_index", 0)
                        return (int(scene_idx), int(variant_idx))
                return (0, 0)

            outputs.sort(key=_get_sort_key)

        return outputs

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _finalize_execution(self, execution_id: str) -> None:
        """根据任务最终状态确定并更新 execution 的终态。

        规则：
        - 已处于终态（completed/failed/cancelled）则不再更新
        - 有 failed 或 skipped -> execution 为 failed
        - 有 cancelled -> execution 为 cancelled
        - 全部 completed -> execution 为 completed
        """
        conn = get_connection()

        # 如果 execution 已处于终态，不再覆盖
        exec_row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", (execution_id,)
        ).fetchone()
        if exec_row and exec_row["status"] in ("completed", "failed", "cancelled"):
            return

        stats = conn.execute(
            "SELECT status, COUNT(*) as cnt "
            "FROM tasks WHERE execution_id = ? GROUP BY status",
            (execution_id,),
        ).fetchall()
        status_counts = {r["status"]: r["cnt"] for r in stats}

        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        skipped = status_counts.get("skipped", 0)
        cancelled = status_counts.get("cancelled", 0)
        total = sum(status_counts.values())

        # 确定终态
        if failed > 0 or skipped > 0:
            new_status = "failed"
        elif cancelled > 0:
            new_status = "cancelled"
        else:
            new_status = "completed"

        now = _now_iso()
        conn.execute(
            "UPDATE executions SET status = ?, completed_at = ?, "
            "completed_count = ? WHERE id = ?",
            (new_status, now, completed, execution_id),
        )
        conn.commit()

        emit_event(
            execution_id, "", f"execution.{new_status}", new_status,
            message=f"执行{new_status}: {completed}/{total} 任务完成",
        )


# ------------------------------------------------------------------
#  模块级工具函数
# ------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
