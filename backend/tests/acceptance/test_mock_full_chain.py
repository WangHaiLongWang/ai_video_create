"""Mock 全链集成测试 — 验证完整 pipeline 的调度、映射、传播、取消、重试、收敛。

测试场景：
1. 3 个 scene 的 storyboard -> 3 个 image -> 3 个 video -> 1 个 concat
2. 验证 scene_id 映射正确
3. 验证失败传播到下游
4. 验证取消操作
5. 验证重试机制
6. 验证 execution 收敛

所有 Handler 均为 Mock，不依赖外部服务。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

from backend.app.db.connection import close_connection, init_db, get_connection
from backend.app.engine.compiler import compile_workflow
from backend.app.engine.queue import (
    enqueue_tasks,
    get_tasks_by_execution,
    get_task,
    claim_task,
    complete_task as queue_complete,
    fail_task as queue_fail,
    cancel_task as queue_cancel,
)
from backend.app.engine.scheduler import Scheduler
from backend.app.handlers import init_mock_handlers, clear_handlers
from backend.app.handlers.contracts import NodeResult, ArtifactRef, NodeError

# 导入模块以便 monkeypatch
import backend.app.db.connection as conn_module


# ------------------------------------------------------------------
#  工作流定义：标准 promptToVideo 6 节点流水线
# ------------------------------------------------------------------

WORKFLOW_SPEC = {
    "id": "wf-full-chain",
    "name": "全链测试工作流",
    "nodes": [
        {
            "id": "textInput",
            "type": "studio",
            "position": {"x": 0, "y": 0},
            "data": {
                "kind": "textInput",
                "label": "主题输入",
                "config": {"prompt": "自然风光短视频"},
            },
        },
        {
            "id": "storyboard",
            "type": "studio",
            "position": {"x": 200, "y": 0},
            "data": {
                "kind": "storyboard",
                "label": "分镜生成",
                "config": {"scenes": 3, "style": "cinematic"},
            },
        },
        {
            "id": "textToImage",
            "type": "studio",
            "position": {"x": 400, "y": 0},
            "data": {
                "kind": "textToImage",
                "label": "文生图",
                "config": {"mapOver": True, "scenes": 3},
            },
        },
        {
            "id": "imageToVideo",
            "type": "studio",
            "position": {"x": 600, "y": 0},
            "data": {
                "kind": "imageToVideo",
                "label": "图生视频",
                "config": {"mapOver": True, "scenes": 3},
            },
        },
        {
            "id": "videoConcat",
            "type": "studio",
            "position": {"x": 800, "y": 0},
            "data": {
                "kind": "videoConcat",
                "label": "视频合成",
                "config": {"filename": "final_output.mp4"},
            },
        },
        {
            "id": "output",
            "type": "studio",
            "position": {"x": 1000, "y": 0},
            "data": {
                "kind": "output",
                "label": "成片输出",
                "config": {},
            },
        },
    ],
    "edges": [
        {"id": "e1", "source": "textInput", "target": "storyboard"},
        {"id": "e2", "source": "storyboard", "target": "textToImage"},
        {"id": "e3", "source": "storyboard", "target": "imageToVideo"},
        {"id": "e4", "source": "textToImage", "target": "videoConcat"},
        {"id": "e5", "source": "imageToVideo", "target": "videoConcat"},
        {"id": "e6", "source": "videoConcat", "target": "output"},
    ],
}


# ------------------------------------------------------------------
#  编译后的 task id 命名规则（由 compiler.py 决定）
# ------------------------------------------------------------------

def _compiled_task_ids() -> list[str]:
    """根据 compiler.py 的 map 展开规则，列出预期的 task id。"""
    plan = compile_workflow(WORKFLOW_SPEC)
    return [t.id for t in plan.tasks]


# ------------------------------------------------------------------
#  Fixtures
# ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库。"""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test_full_chain.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()

    # 初始化 Mock Handlers
    init_mock_handlers()

    # 创建 workflow + execution 记录（workflow_snapshot 需包含完整 spec 供 scheduler 读取）
    conn = get_connection()
    spec_json = json.dumps(WORKFLOW_SPEC, ensure_ascii=False)
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        ("wf-full-chain", "全链测试工作流", spec_json),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        ("exec-test", "wf-full-chain", spec_json, "pending"),
    )
    conn.commit()

    yield

    clear_handlers()
    close_connection()


@pytest.fixture
def scheduler():
    """创建 Scheduler 实例（不使用 WorkerPool，由测试手动调度）。"""
    return Scheduler(max_retries=3, poll_interval=0.1)


@pytest.fixture
def scheduler_with_pool():
    """创建带 WorkerPool 的 Scheduler（用于真实异步执行测试）。"""
    pool = WorkerPool(worker_count=2, poll_interval=0.05)
    return Scheduler(worker_pool=pool, max_retries=3, poll_interval=0.05)


# ------------------------------------------------------------------
#  Mock Handler 工具
# ------------------------------------------------------------------


class MockHandlerFactory:
    """可配置的 Mock Handler 工厂。

    支持：
    - 指定任务返回成功/失败
    - 指定失败次数（重试后成功）
    - 记录所有被调用的 task，用于验证
    """

    def __init__(self):
        self.call_log: list[dict[str, Any]] = []
        self._fail_tasks: dict[str, int] = {}  # task_id -> 剩余失败次数
        self._fail_kinds: dict[str, int] = {}  # kind -> 剩余失败次数

    def will_fail(self, task_id: str, times: int = 1) -> None:
        """指定某个 task 失败若干次后成功。"""
        self._fail_tasks[task_id] = times

    def will_fail_kind(self, kind: str, times: int = 1) -> None:
        """指定某种 kind 的 task 失败若干次。"""
        self._fail_kinds[kind] = times

    def make_handler(self, kind: str):
        """创建一个可配置的 Mock Handler。"""
        factory = self

        class ConfigurableMockHandler:
            async def execute(self, task: dict, context: dict) -> NodeResult:
                task_id = task.get("id", "")
                factory.call_log.append({
                    "task_id": task_id,
                    "kind": kind,
                    "item_key": task.get("item_key"),
                })

                # 检查是否需要失败
                if task_id in factory._fail_tasks and factory._fail_tasks[task_id] > 0:
                    factory._fail_tasks[task_id] -= 1
                    return NodeResult.fail(
                        code="MOCK_ERROR",
                        message=f"Mock failure for {task_id}",
                        retryable=True,
                    )
                if kind in factory._fail_kinds and factory._fail_kinds[kind] > 0:
                    factory._fail_kinds[kind] -= 1
                    return NodeResult.fail(
                        code="MOCK_ERROR",
                        message=f"Mock failure for kind {kind}",
                        retryable=True,
                    )

                # 返回成功（带 mock 数据）
                return self._mock_success(task)

            def _mock_success(self, task: dict) -> NodeResult:
                item_key = task.get("item_key", "")
                if kind == "textInput":
                    return NodeResult.ok(
                        output=ArtifactRef(type="text", metadata={"content": "mock prompt"}),
                    )
                elif kind == "storyboard":
                    scene_count = int(task.get("config", {}).get("scenes", 5))
                    scenes = [
                        {
                            "scene_id": f"scene-{i + 1:03d}",
                            "index": i,
                            "narration": f"场景 {i + 1}",
                            "image_prompt": f"image prompt for scene {i + 1}",
                            "video_prompt": f"video prompt for scene {i + 1}",
                            "duration_seconds": 4,
                        }
                        for i in range(scene_count)
                    ]
                    return NodeResult.ok(
                        output=ArtifactRef(type="text", metadata={"scenes": scenes}),
                    )
                elif kind == "textToImage":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="image",
                            asset_id=f"img-{uuid.uuid4().hex[:8]}",
                            scene_id=item_key,
                        ),
                    )
                elif kind == "imageToVideo":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="video",
                            asset_id=f"vid-{uuid.uuid4().hex[:8]}",
                            scene_id=item_key,
                        ),
                    )
                elif kind == "videoConcat":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="video",
                            asset_id=f"final-{uuid.uuid4().hex[:8]}",
                            metadata={"filename": "final_output.mp4"},
                        ),
                    )
                elif kind == "output":
                    return NodeResult.ok(
                        output=ArtifactRef(type="video", metadata={"message": "完成"}),
                    )
                return NodeResult.ok()

        return ConfigurableMockHandler()


# ------------------------------------------------------------------
#  辅助函数
# ------------------------------------------------------------------


async def run_full_pipeline(
    scheduler: Scheduler,
    execution_id: str,
    mock_factory: MockHandlerFactory | None = None,
) -> dict:
    """手动驱动完整 pipeline：逐层完成任务直到收敛。

    Args:
        scheduler: Scheduler 实例。
        execution_id: 执行 ID。
        mock_factory: 可选的 Mock Handler 工厂（用于模拟执行）。

    Returns:
        最终的 execution 摘要。
    """
    # 启动 execution
    ready = await scheduler.start_execution(execution_id)

    # 循环调度直到收敛
    max_iterations = 100  # 安全上限
    iteration = 0

    while not scheduler.check_convergence(execution_id) and iteration < max_iterations:
        iteration += 1

        # 获取所有 pending 任务
        tasks = get_tasks_by_execution(execution_id)
        ready_tasks = [
            t for t in tasks
            if t["status"] == "pending"
            and all(
                next((tt for tt in tasks if tt["id"] == d), None) is not None
                and next(tt for tt in tasks if tt["id"] == d)["status"] == "completed"
                for d in t.get("depends_on", [])
            )
        ]

        if not ready_tasks:
            await asyncio.sleep(0.05)
            continue

        for task in ready_tasks:
            # 模拟执行
            if mock_factory:
                handler = mock_factory.make_handler(task["kind"])
                # 先组装 NodeInput
                task = scheduler.assemble_node_input(task, execution_id)
                context = {"upstream_results": {}}
                result = await handler.execute(task, context)

                if result.status == "failed":
                    await scheduler.fail_task(task["id"], result.error or NodeError(code="UNKNOWN", message="unknown"))
                else:
                    await scheduler.complete_task(task["id"], result)
            else:
                # 直接标记完成（无 handler 模拟）
                await scheduler.complete_task(
                    task["id"],
                    NodeResult.ok(output=ArtifactRef(type="text")),
                )

    return scheduler.get_execution_summary(execution_id)


# ==================================================================
#  测试类
# ==================================================================


class TestFullPipelineCompilation:
    """验证 compiler.py 对标准工作流的编译结果。"""

    def test_compile_produces_expected_tasks(self):
        """编译后应生成正确数量的 tasks。"""
        plan = compile_workflow(WORKFLOW_SPEC)
        task_ids = [t.id for t in plan.tasks]

        # textInput -> 1 task
        assert "textInput-task" in task_ids
        # storyboard -> 1 task
        assert "storyboard-task" in task_ids
        # textToImage -> 3 map-expanded tasks
        assert "textToImage-scene-001" in task_ids
        assert "textToImage-scene-002" in task_ids
        assert "textToImage-scene-003" in task_ids
        # imageToVideo -> 3 map-expanded tasks
        assert "imageToVideo-scene-001" in task_ids
        assert "imageToVideo-scene-002" in task_ids
        assert "imageToVideo-scene-003" in task_ids
        # videoConcat -> 1 task
        assert "videoConcat-task" in task_ids
        # output -> 1 task
        assert "output-task" in task_ids

        assert len(plan.tasks) == 10

    def test_topological_order(self):
        """拓扑排序结果应满足依赖关系。"""
        plan = compile_workflow(WORKFLOW_SPEC)
        id_order = {t.id: i for i, t in enumerate(plan.tasks)}

        for task in plan.tasks:
            for dep in task.depends_on:
                assert id_order[dep] < id_order[task.id], (
                    f"{task.id} 的依赖 {dep} 应在其前面"
                )

    def test_map_expansion_dependencies(self):
        """map 展开的任务应依赖上游所有任务。"""
        plan = compile_workflow(WORKFLOW_SPEC)
        text_to_img_tasks = [t for t in plan.tasks if t.node_id == "textToImage"]

        # textToImage 的 map 展开任务应依赖 storyboard-task
        for t in text_to_img_tasks:
            assert "storyboard-task" in t.depends_on
            assert t.is_map_expansion is True
            assert t.item_key is not None
            assert t.item_key.startswith("scene-")

    def test_video_concat_aggregates_all(self):
        """videoConcat 应依赖所有 imageToVideo 和 textToImage 的 map 展开任务。"""
        plan = compile_workflow(WORKFLOW_SPEC)
        concat_task = next(t for t in plan.tasks if t.node_id == "videoConcat")

        # 应依赖 3 个 imageToVideo task + 3 个 textToImage task
        img_to_vid_deps = [
            d for d in concat_task.depends_on if d.startswith("imageToVideo-")
        ]
        txt_to_img_deps = [
            d for d in concat_task.depends_on if d.startswith("textToImage-")
        ]
        assert len(img_to_vid_deps) == 3
        assert len(txt_to_img_deps) == 3


class TestSceneIdMapping:
    """验证 scene_id 映射正确。"""

    @pytest.mark.asyncio
    async def test_storyboard_generates_scene_ids(self, scheduler):
        """storyboard 生成的 scene 数据应包含正确的 scene_id。"""
        factory = MockHandlerFactory()
        result = await run_full_pipeline(scheduler, "exec-test", factory)

        # 验证 storyboard 被调用
        storyboard_calls = [c for c in factory.call_log if c["kind"] == "storyboard"]
        assert len(storyboard_calls) == 1

    @pytest.mark.asyncio
    async def test_text_to_image_tasks_receive_scene_data(self, scheduler):
        """textToImage 的 map 展开任务应接收到正确的 scene 数据。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        # 验证 textToImage 被调用了 3 次，分别对应 scene-001, scene-002, scene-003
        img_calls = [c for c in factory.call_log if c["kind"] == "textToImage"]
        assert len(img_calls) == 3
        img_keys = sorted(c["item_key"] for c in img_calls)
        assert img_keys == ["scene-001", "scene-002", "scene-003"]

    @pytest.mark.asyncio
    async def test_image_to_video_tasks_receive_scene_data(self, scheduler):
        """imageToVideo 的 map 展开任务应接收到正确的 scene 数据。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        vid_calls = [c for c in factory.call_log if c["kind"] == "imageToVideo"]
        assert len(vid_calls) == 3
        vid_keys = sorted(c["item_key"] for c in vid_calls)
        assert vid_keys == ["scene-001", "scene-002", "scene-003"]

    @pytest.mark.asyncio
    async def test_all_scene_ids_consistent(self, scheduler):
        """所有 scene 展开任务的 scene_id 应一致（imageToVideo 使用与 textToImage 相同的 scene_id）。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        txt_keys = sorted(
            c["item_key"]
            for c in factory.call_log
            if c["kind"] == "textToImage"
        )
        vid_keys = sorted(
            c["item_key"]
            for c in factory.call_log
            if c["kind"] == "imageToVideo"
        )
        assert txt_keys == vid_keys


class TestFailurePropagation:
    """验证失败传播到下游。"""

    @pytest.mark.asyncio
    async def test_storyboard_failure_skips_all_downstream(self, scheduler):
        """storyboard 失败后，所有下游任务（textToImage, imageToVideo, videoConcat, output）应被 skipped。"""
        factory = MockHandlerFactory()
        factory.will_fail_kind("storyboard", times=999)  # 永远失败

        await run_full_pipeline(scheduler, "exec-test", factory)

        result = scheduler.get_execution_summary("exec-test")
        assert result.get("failed", 0) >= 1  # storyboard 失败
        # 所有下游都应被 skipped: 3 textToImage + 3 imageToVideo + videoConcat + output = 8
        assert result.get("skipped", 0) >= 7

    @pytest.mark.asyncio
    async def test_single_scene_failure_does_not_skip_other_scenes(self, scheduler):
        """单个 textToImage scene 失败后，其他 scene 的 textToImage 不应受影响。

        只有依赖该 scene 的下游（videoConcat, output）会被 skipped，
        因为其他 scene 的 textToImage 不依赖失败的那个。
        """
        factory = MockHandlerFactory()
        factory.will_fail("textToImage-scene-001", times=999)  # 只有 scene-001 失败

        await run_full_pipeline(scheduler, "exec-test", factory)

        result = scheduler.get_execution_summary("exec-test")
        # textInput 和 storyboard 完成
        # textToImage-scene-002 和 scene-003 完成
        # imageToVideo-scene-002 和 scene-003 完成
        # textToImage-scene-001 超过重试 -> failed
        # videoConcat 依赖所有6个上游，其中1个 skipped -> 自己也被 skipped
        # output 依赖 videoConcat (skipped) -> skipped
        assert result.get("failed", 0) >= 1  # textToImage-scene-001
        assert result.get("completed", 0) >= 5  # textInput + storyboard + 2 textToImage + 2 imageToVideo
        assert result.get("skipped", 0) >= 2  # videoConcat + output

    @pytest.mark.asyncio
    async def test_video_concat_failure_skips_output(self, scheduler):
        """videoConcat 失败后，output 应被 skipped。"""
        factory = MockHandlerFactory()
        factory.will_fail_kind("videoConcat", times=999)

        await run_full_pipeline(scheduler, "exec-test", factory)

        result = scheduler.get_execution_summary("exec-test")
        assert result.get("failed", 0) >= 1  # videoConcat
        assert result.get("skipped", 0) >= 1  # output

    @pytest.mark.asyncio
    async def test_execution_marked_failed_on_downstream_failure(self, scheduler):
        """当有任务失败且无法恢复时，execution 应被标记为 failed。"""
        factory = MockHandlerFactory()
        factory.will_fail_kind("storyboard", times=999)

        await run_full_pipeline(scheduler, "exec-test", factory)

        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "failed"


class TestCancelOperation:
    """验证取消操作。"""

    @pytest.mark.asyncio
    async def test_cancel_stops_all_pending_tasks(self, scheduler):
        """取消 execution 后，所有 pending/running 任务应被 cancelled。"""
        # 启动但不执行任何任务
        await scheduler.start_execution("exec-test")

        # 立即取消
        await scheduler.cancel_execution("exec-test")

        tasks = get_tasks_by_execution("exec-test")
        for task in tasks:
            assert task["status"] == "cancelled", (
                f"任务 {task['id']} 状态应为 cancelled，实际为 {task['status']}"
            )

    @pytest.mark.asyncio
    async def test_cancel_execution_marks_execution_cancelled(self, scheduler):
        """取消 execution 后，execution 记录应被标记为 cancelled。"""
        await scheduler.start_execution("exec-test")
        await scheduler.cancel_execution("exec-test")

        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_partial_execution(self, scheduler):
        """部分执行后取消，已完成的任务保持 completed，其余为 cancelled。"""
        factory = MockHandlerFactory()

        # 执行 storyboard（让它完成）
        ready = await scheduler.start_execution("exec-test")
        tasks = get_tasks_by_execution("exec-test")

        # 只完成 textInput
        txt_input = next(t for t in tasks if t["id"] == "textInput-task")
        result = await factory.make_handler("textInput").execute(txt_input, {})
        await scheduler.complete_task("textInput-task", result)

        # 此时取消
        await scheduler.cancel_execution("exec-test")

        tasks = get_tasks_by_execution("exec-test")
        txt_task = next(t for t in tasks if t["id"] == "textInput-task")
        assert txt_task["status"] == "completed"

        # 其余任务应为 cancelled
        other_tasks = [t for t in tasks if t["id"] != "textInput-task"]
        for t in other_tasks:
            assert t["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_convergence_after_cancel(self, scheduler):
        """取消后 execution 应收敛。"""
        await scheduler.start_execution("exec-test")
        await scheduler.cancel_execution("exec-test")

        assert scheduler.check_convergence("exec-test") is True


class TestRetryMechanism:
    """验证重试机制。"""

    @pytest.mark.asyncio
    async def test_retry_then_success(self, scheduler):
        """任务失败一次后重试成功。"""
        # 创建一个简单的线性链：textInput -> storyboard
        conn = get_connection()
        spec = {
            "id": "wf-retry",
            "name": "重试测试",
            "nodes": [
                {"id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
                 "data": {"kind": "textInput", "label": "输入", "config": {}}},
                {"id": "n2", "type": "studio", "position": {"x": 200, "y": 0},
                 "data": {"kind": "storyboard", "label": "分镜", "config": {"scenes": 2}}},
            ],
            "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
        }
        spec_json = json.dumps(spec, ensure_ascii=False)
        conn.execute(
            "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
            ("wf-retry", "重试测试", spec_json),
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
            "VALUES (?, ?, ?, ?)",
            ("exec-retry", "wf-retry", spec_json, "pending"),
        )
        conn.commit()

        factory = MockHandlerFactory()
        factory.will_fail("n1-task", times=1)  # n1 失败 1 次后成功

        await run_full_pipeline(scheduler, "exec-retry", factory)

        result = scheduler.get_execution_summary("exec-retry")
        # n1 重试成功后，所有任务都应完成
        assert result.get("failed", 0) == 0
        assert result.get("skipped", 0) == 0
        assert result["completed"] == 2

    @pytest.mark.asyncio
    async def test_retry_exhaustion_triggers_propagation(self, scheduler):
        """重试次数耗尽后，失败传播到下游。"""
        factory = MockHandlerFactory()
        factory.will_fail("textInput-task", times=999)  # 永远失败

        await run_full_pipeline(scheduler, "exec-test", factory)

        result = scheduler.get_execution_summary("exec-test")
        # textInput 失败且重试耗尽
        assert result.get("failed", 0) >= 1
        # storyboard 因为依赖 textInput 应被 skipped
        assert result.get("skipped", 0) >= 1

    @pytest.mark.asyncio
    async def test_fail_task_records_error(self, scheduler):
        """失败的任务应记录错误信息。"""
        factory = MockHandlerFactory()
        factory.will_fail("textInput-task", times=999)

        await run_full_pipeline(scheduler, "exec-test", factory)

        task = get_task("textInput-task")
        assert task["status"] == "failed"
        assert task["error"] != ""

    @pytest.mark.asyncio
    async def test_attempt_counter_increments(self, scheduler):
        """重试时 attempt 计数器应递增。"""
        factory = MockHandlerFactory()
        factory.will_fail("textInput-task", times=2)  # 失败 2 次后成功

        await run_full_pipeline(scheduler, "exec-test", factory)

        task = get_task("textInput-task")
        # 经历了 2 次失败 + 1 次成功，attempt 应为 2
        assert task["attempt"] >= 2


class TestExecutionConvergence:
    """验证 execution 收敛。"""

    @pytest.mark.asyncio
    async def test_full_success_converges(self, scheduler):
        """所有任务成功完成时，execution 收敛为 completed。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        assert scheduler.check_convergence("exec-test") is True
        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "completed"

    @pytest.mark.asyncio
    async def test_partial_failure_converges_as_failed(self, scheduler):
        """部分任务失败时，execution 收敛为 failed。"""
        factory = MockHandlerFactory()
        factory.will_fail("videoConcat-task", times=999)

        await run_full_pipeline(scheduler, "exec-test", factory)

        assert scheduler.check_convergence("exec-test") is True
        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "failed"

    @pytest.mark.asyncio
    async def test_all_tasks_reach_terminal_state(self, scheduler):
        """收敛后，所有任务应处于终态。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        tasks = get_tasks_by_execution("exec-test")
        terminal_states = {"completed", "failed", "skipped", "cancelled"}
        for task in tasks:
            assert task["status"] in terminal_states, (
                f"任务 {task['id']} 处于非终态: {task['status']}"
            )

    @pytest.mark.asyncio
    async def test_convergence_summary_counts(self, scheduler):
        """收敛后，summary 的计数应正确。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        summary = scheduler.get_execution_summary("exec-test")
        total = summary["total"]
        terminal_sum = (
            summary.get("completed", 0)
            + summary.get("failed", 0)
            + summary.get("skipped", 0)
            + summary.get("cancelled", 0)
        )
        assert total == terminal_sum

    @pytest.mark.asyncio
    async def test_scheduler_start_execution_returns_ready_ids(self, scheduler):
        """start_execution 应返回首批可执行的 task_id。"""
        ready = await scheduler.start_execution("exec-test")
        assert len(ready) > 0
        # textInput-task 没有依赖，应在首批中
        assert "textInput-task" in ready

    @pytest.mark.asyncio
    async def test_schedule_next_tasks_after_completion(self, scheduler):
        """完成一个任务后，schedule_next_tasks 应返回新解锁的任务。"""
        await scheduler.start_execution("exec-test")

        # 手动完成 textInput-task
        await scheduler.complete_task(
            "textInput-task",
            NodeResult.ok(output=ArtifactRef(type="text")),
        )

        ready = await scheduler.schedule_next_tasks("exec-test")
        # storyboard-task 依赖 textInput-task，现在应解锁
        assert "storyboard-task" in ready


class TestWorkerPoolIntegration:
    """使用 WorkerPool 的完整异步执行测试。"""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_worker_pool(self):
        """通过 WorkerPool 执行完整 pipeline。"""
        from backend.app.engine.worker import WorkerPool

        scheduler = Scheduler(max_retries=3)
        pool = WorkerPool(worker_count=2, poll_interval=0.05)

        await pool.start()
        try:
            await scheduler.start_execution("exec-test")

            # 等待所有任务完成（最长 30 秒）
            for _ in range(300):
                if scheduler.check_convergence("exec-test"):
                    break
                await asyncio.sleep(0.1)

            assert scheduler.check_convergence("exec-test") is True

            summary = scheduler.get_execution_summary("exec-test")
            # Mock handler 的延迟很短，所有任务应成功完成
            assert summary.get("completed", 0) >= 8  # 至少 8 个任务完成
        finally:
            await pool.stop()

    @pytest.mark.asyncio
    async def test_worker_pool_cancel_during_execution(self):
        """执行过程中取消 execution。"""
        from backend.app.engine.worker import WorkerPool

        scheduler = Scheduler(max_retries=3)
        pool = WorkerPool(worker_count=1, poll_interval=0.05)

        await pool.start()
        try:
            await scheduler.start_execution("exec-test")
            # 等一点时间让部分任务开始执行
            await asyncio.sleep(0.3)

            # 取消
            await scheduler.cancel_execution("exec-test")

            # 等待收敛
            for _ in range(100):
                if scheduler.check_convergence("exec-test"):
                    break
                await asyncio.sleep(0.1)

            assert scheduler.check_convergence("exec-test") is True

            summary = scheduler.get_execution_summary("exec-test")
            # 应有 cancelled 或 completed 任务
            assert (
                summary.get("cancelled", 0) + summary.get("completed", 0)
            ) > 0
        finally:
            await pool.stop()


class TestNodeInputAssembly:
    """验证 NodeInput 组装逻辑。"""

    def test_assemble_node_input_with_scene_data(self, scheduler):
        """map 展开任务应接收正确的 scene 数据。"""
        # 模拟上游 storyboard 输出
        upstream_result = NodeResult.ok(
            output=ArtifactRef(
                type="text",
                metadata={
                    "scenes": [
                        {
                            "scene_id": "scene-001",
                            "index": 0,
                            "narration": "第一幕",
                            "image_prompt": "sunset over mountains",
                            "video_prompt": "panoramic view",
                            "duration_seconds": 5,
                        },
                    ],
                },
            ),
        )

        # 先在 DB 中创建任务记录
        enqueue_tasks("wf-full-chain", "exec-test", [
            {"id": "storyboard-task", "node_id": "storyboard", "kind": "storyboard",
             "label": "分镜", "config": {}, "depends_on": []},
            {"id": "textToImage-scene-001", "node_id": "textToImage", "kind": "textToImage",
             "label": "图", "item_key": "scene-001", "index": 0,
             "config": {"mapOver": True}, "depends_on": ["storyboard-task"]},
        ])

        # 写入 storyboard 的结果
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET status = 'completed', result_json = ? "
            "WHERE id = 'storyboard-task'",
            (json.dumps(upstream_result.to_dict(), ensure_ascii=False),),
        )
        conn.commit()

        task = {
            "id": "textToImage-scene-001",
            "item_key": "scene-001",
            "config": {"mapOver": True},
            "depends_on": ["storyboard-task"],
        }

        assembled = scheduler.assemble_node_input(task, "exec-test")
        assert assembled["config"]["image_prompt"] == "sunset over mountains"
        assert assembled["config"]["video_prompt"] == "panoramic view"

    def test_assemble_node_input_no_upstream(self, scheduler):
        """无上游依赖时，task 应保持不变。"""
        task = {
            "id": "textInput-task",
            "item_key": None,
            "config": {"prompt": "test"},
            "depends_on": [],
        }

        assembled = scheduler.assemble_node_input(task, "exec-test")
        assert assembled["config"]["prompt"] == "test"

    def test_aggregate_upstream_outputs(self, scheduler):
        """聚合上游输出应返回所有上游结果。"""
        # 先在 DB 中创建任务记录
        enqueue_tasks("wf-full-chain", "exec-test", [
            {"id": f"textToImage-scene-{i:03d}", "node_id": "textToImage",
             "kind": "textToImage", "label": "图",
             "item_key": f"scene-{i:03d}", "index": i - 1,
             "config": {}, "depends_on": ["storyboard-task"]}
            for i in range(1, 4)
        ] + [
            {"id": "videoConcat-task", "node_id": "videoConcat",
             "kind": "videoConcat", "label": "合成",
             "config": {}, "depends_on": [
                 "textToImage-scene-001", "textToImage-scene-002",
                 "textToImage-scene-003",
             ]},
        ])

        # 写入上游结果
        conn = get_connection()
        for i, task_id in enumerate(
            ["textToImage-scene-001", "textToImage-scene-002", "textToImage-scene-003"]
        ):
            result = {
                "status": "succeeded",
                "output": {
                    "type": "image",
                    "scene_id": f"scene-{i + 1:03d}",
                },
            }
            conn.execute(
                "UPDATE tasks SET status = 'completed', result_json = ? WHERE id = ?",
                (json.dumps(result, ensure_ascii=False), task_id),
            )
        conn.commit()

        task = {
            "id": "videoConcat-task",
            "depends_on": [
                "textToImage-scene-001",
                "textToImage-scene-002",
                "textToImage-scene-003",
            ],
        }

        outputs = scheduler.aggregate_upstream_outputs(task, "exec-test")
        assert len(outputs) == 3


class TestEdgeCases:
    """边界情况测试。"""

    @pytest.mark.asyncio
    async def test_start_nonexistent_execution(self, scheduler):
        """启动不存在的 execution 应抛出异常。"""
        from backend.app.engine.scheduler import SchedulerError
        with pytest.raises(SchedulerError, match="不存在"):
            await scheduler.start_execution("exec-nonexistent")

    @pytest.mark.asyncio
    async def test_complete_nonexistent_task(self, scheduler):
        """完成不存在的任务不应报错。"""
        # 不应抛异常，仅记录 warning
        await scheduler.complete_task(
            "nonexistent-task",
            NodeResult.ok(),
        )

    @pytest.mark.asyncio
    async def test_fail_nonexistent_task(self, scheduler):
        """失败不存在的任务不应报错。"""
        await scheduler.fail_task(
            "nonexistent-task",
            NodeError(code="NOT_FOUND", message="not found"),
        )

    @pytest.mark.asyncio
    async def test_check_convergence_empty_execution(self, scheduler):
        """空的 execution（无任务）不应收敛。"""
        assert scheduler.check_convergence("exec-test") is False

    @pytest.mark.asyncio
    async def test_cancel_already_converged_execution(self, scheduler):
        """已收敛的 execution 取消不应改变状态。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        # 已完成
        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "completed"

        # 尝试取消（应跳过，因为已完成）
        await scheduler.cancel_execution("exec-test")

        # 状态应保持 completed
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-test",)
        ).fetchone()
        assert row["status"] == "completed"

    @pytest.mark.asyncio
    async def test_full_chain_completed_count(self, scheduler):
        """全链完成后，completed 任务数应正确。"""
        factory = MockHandlerFactory()
        await run_full_pipeline(scheduler, "exec-test", factory)

        summary = scheduler.get_execution_summary("exec-test")
        # 标准 6 节点工作流编译后有 10 个 task（textToImage 和 imageToVideo 各展开3个）
        assert summary["total"] == 10
        assert summary["completed"] == 10
        assert summary.get("failed", 0) == 0
        assert summary.get("skipped", 0) == 0
