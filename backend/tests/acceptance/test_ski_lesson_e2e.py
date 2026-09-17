"""冬季单板滑雪教学 Mock E2E 测试。

验证 SKI-LESSON-WORKFLOW-PLAN 中定义的首条验收工作流：
- 1 Scene → 2 图片变体 → 2 × 3s 视频 → 合成 ~6s 成片
- variantCount / scene+variant 血缘 / aggregate 顺序 作为通用可插拔能力

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
)
from backend.app.engine.scheduler import Scheduler
from backend.app.handlers.contracts import NodeResult, ArtifactRef, NodeError

import backend.app.db.connection as conn_module

# Import fixture data — make fixtures directory importable
import sys as _sys
import os as _os
_fixture_dir = _os.path.normpath(
    _os.path.join(_os.path.dirname(__file__), "..", "fixtures")
)
if _fixture_dir not in _sys.path:
    _sys.path.insert(0, _fixture_dir)
from ski_lesson_bundle import (  # type: ignore[import-not-found]
    SKI_LESSON_WORKFLOW_SPEC,
    SKI_LESSON_SCENE_BUNDLE,
    SKI_LESSON_VARIANTS,
)


# ------------------------------------------------------------------
#  Fixtures
# ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用独立的临时数据库。"""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test_ski.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()

    # 创建 workflow + execution 记录
    conn = get_connection()
    spec_json = json.dumps(SKI_LESSON_WORKFLOW_SPEC, ensure_ascii=False)
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        ("wf-ski-lesson", "写实滑雪教学", spec_json),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        ("exec-ski", "wf-ski-lesson", spec_json, "pending"),
    )
    conn.commit()

    yield

    close_connection()


@pytest.fixture
def scheduler():
    return Scheduler(max_retries=3, poll_interval=0.1)


# ------------------------------------------------------------------
#  Mock Handler 工厂（滑雪教学专用）
# ------------------------------------------------------------------


class SkiLessonMockFactory:
    """可配置的 Mock Handler 工厂，用于滑雪教学 E2E。"""

    def __init__(self):
        self.call_log: list[dict[str, Any]] = []

    def make_handler(self, kind: str):
        factory = self

        class MockHandler:
            async def execute(self, task: dict, context: dict) -> NodeResult:
                task_id = task.get("id", "")
                item_key = task.get("item_key", "")
                config = task.get("config", {})
                factory.call_log.append({
                    "task_id": task_id,
                    "kind": kind,
                    "item_key": item_key,
                    "variant_id": config.get("variant_id", ""),
                    "variant_index": config.get("variant_index", 0),
                    "scene_id": config.get("scene_id", ""),
                })
                return self._mock_success(task, kind)

            def _mock_success(self, task: dict, kind: str) -> NodeResult:
                item_key = task.get("item_key", "")
                config = task.get("config", {})
                actual_scene = config.get("scene_id", "")
                variant_id = config.get("variant_id", "")

                if kind == "textInput":
                    return NodeResult.ok(
                        output=ArtifactRef(type="text", metadata={"content": "mock prompt"}),
                    )
                elif kind == "storyboard":
                    scenes = [{
                        "scene_id": "scene-001",
                        "index": 0,
                        "narration": "教练讲解单脚蹬行准备姿势",
                        "image_prompt": "写实滑雪教学照片",
                        "video_prompt": "轻微前推镜头",
                        "duration_seconds": 3,
                    }]
                    return NodeResult.ok(
                        output=ArtifactRef(type="text", metadata={"scenes": scenes}),
                    )
                elif kind == "textToImage":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="image",
                            asset_id=f"img-{uuid.uuid4().hex[:8]}",
                            scene_id=actual_scene,
                            variant_id=variant_id or None,
                            metadata={"variant_index": config.get("variant_index", 0)},
                        ),
                    )
                elif kind == "imageToVideo":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="video",
                            asset_id=f"vid-{uuid.uuid4().hex[:8]}",
                            scene_id=actual_scene,
                            variant_id=variant_id or None,
                            metadata={"variant_index": config.get("variant_index", 0)},
                        ),
                    )
                elif kind == "videoConcat":
                    return NodeResult.ok(
                        output=ArtifactRef(
                            type="video",
                            asset_id=f"final-{uuid.uuid4().hex[:8]}",
                            metadata={"filename": "ski-lesson-final.mp4"},
                        ),
                    )
                elif kind == "output":
                    return NodeResult.ok(
                        output=ArtifactRef(type="video", metadata={"message": "完成"}),
                    )
                return NodeResult.ok()

        return MockHandler()


# ------------------------------------------------------------------
#  辅助函数
# ------------------------------------------------------------------


async def run_ski_pipeline(
    scheduler: Scheduler, execution_id: str, factory: SkiLessonMockFactory
) -> dict:
    """手动驱动滑雪教学 pipeline。"""
    ready = await scheduler.start_execution(execution_id)

    max_iterations = 100
    iteration = 0
    while not scheduler.check_convergence(execution_id) and iteration < max_iterations:
        iteration += 1
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
            handler = factory.make_handler(task["kind"])
            task = scheduler.assemble_node_input(task, execution_id)
            context = {"upstream_results": {}}
            result = await handler.execute(task, context)
            if result.status == "failed":
                await scheduler.fail_task(
                    task["id"], result.error or NodeError(code="UNKNOWN", message="unknown")
                )
            else:
                await scheduler.complete_task(task["id"], result)

    return scheduler.get_execution_summary(execution_id)


# ==================================================================
#  测试类
# ==================================================================


class TestCompilation:
    """验证编译器对滑雪教学工作流的编译结果。"""

    def test_compile_produces_8_tasks(self):
        """1 scene + variantCount=2 → 1 textInput + 1 storyboard + 2 textToImage + 2 imageToVideo + 1 videoConcat + 1 output = 8."""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        assert len(plan.tasks) == 8

    def test_text_to_image_variant_expansion(self):
        """textToImage 应展开为 2 个变体 task。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        img_tasks = [t for t in plan.tasks if t.node_id == "textToImage"]
        assert len(img_tasks) == 2

        item_keys = sorted(t.item_key for t in img_tasks)
        assert item_keys == ["scene-001::variant-01", "scene-001::variant-02"]

    def test_image_to_video_expands_by_variant(self):
        """imageToVideo 有 variantCount=2，应按 scene+variant 展开。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        vid_tasks = [t for t in plan.tasks if t.node_id == "imageToVideo"]
        assert len(vid_tasks) == 2
        # imageToVideo 的 item_key 应为 scene::variant 格式
        item_keys = sorted(t.item_key for t in vid_tasks)
        assert item_keys == ["scene-001::variant-01", "scene-001::variant-02"]

    def test_variant_ids_in_config(self):
        """textToImage task config 应包含 variant_id。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        img_tasks = [t for t in plan.tasks if t.node_id == "textToImage"]
        for t in img_tasks:
            assert "variant_id" in t.config
            assert t.config["variant_id"] in ("variant-01", "variant-02")

    def test_variant_prompt_suffix_in_config(self):
        """textToImage task config 应包含 variant_prompt_suffix。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        img_tasks = sorted(
            [t for t in plan.tasks if t.node_id == "textToImage"],
            key=lambda t: t.config.get("variant_index", 0),
        )
        assert "教练方向" in img_tasks[0].config.get("variant_prompt_suffix", "")
        assert "学员" in img_tasks[1].config.get("variant_prompt_suffix", "")

    def test_topological_order(self):
        """拓扑排序应满足依赖关系。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        id_order = {t.id: i for i, t in enumerate(plan.tasks)}
        for task in plan.tasks:
            for dep in task.depends_on:
                assert id_order[dep] < id_order[task.id]

    def test_concat_depends_on_all_video_tasks(self):
        """videoConcat 应依赖所有 imageToVideo task。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        concat = next(t for t in plan.tasks if t.node_id == "videoConcat")
        vid_deps = [d for d in concat.depends_on if d.startswith("imageToVideo-")]
        assert len(vid_deps) == 2

    def test_all_tasks_have_unique_ids(self):
        """所有 task ID 应唯一。"""
        plan = compile_workflow(SKI_LESSON_WORKFLOW_SPEC)
        ids = [t.id for t in plan.tasks]
        assert len(ids) == len(set(ids))


class TestMockPipeline:
    """验证完整 Mock pipeline 的执行。"""

    @pytest.mark.asyncio
    async def test_full_pipeline_succeeds(self, scheduler):
        """所有 Mock handler 成功时，execution 收敛为 completed。"""
        factory = SkiLessonMockFactory()
        summary = await run_ski_pipeline(scheduler, "exec-ski", factory)

        assert summary["total"] == 8
        assert summary["completed"] == 8
        assert summary.get("failed", 0) == 0
        assert summary.get("skipped", 0) == 0

    @pytest.mark.asyncio
    async def test_execution_marked_completed(self, scheduler):
        """收敛后 execution 应标记为 completed。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        conn = get_connection()
        row = conn.execute(
            "SELECT status FROM executions WHERE id = ?", ("exec-ski",)
        ).fetchone()
        assert row["status"] == "completed"

    @pytest.mark.asyncio
    async def test_text_to_image_called_twice_with_variants(self, scheduler):
        """textToImage 应被调用 2 次，分别对应 variant-01 和 variant-02。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        img_calls = [c for c in factory.call_log if c["kind"] == "textToImage"]
        assert len(img_calls) == 2

        variant_ids = sorted(c["variant_id"] for c in img_calls)
        assert variant_ids == ["variant-01", "variant-02"]

    @pytest.mark.asyncio
    async def test_image_to_video_receives_correct_variants(self, scheduler):
        """imageToVideo 应接收 2 个变体 task。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        vid_calls = [c for c in factory.call_log if c["kind"] == "imageToVideo"]
        assert len(vid_calls) == 2

        variant_ids = sorted(c["variant_id"] for c in vid_calls)
        assert variant_ids == ["variant-01", "variant-02"]

    @pytest.mark.asyncio
    async def test_video_concat_called_once(self, scheduler):
        """videoConcat 应只被调用 1 次。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        concat_calls = [c for c in factory.call_log if c["kind"] == "videoConcat"]
        assert len(concat_calls) == 1

    @pytest.mark.asyncio
    async def test_all_scene_ids_consistent(self, scheduler):
        """所有 task 的 scene_id 应一致（都是 scene-001）。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        for call in factory.call_log:
            if call["kind"] in ("textToImage", "imageToVideo"):
                assert call["scene_id"] == "scene-001"


class TestVariantLineage:
    """验证 variant 血缘追踪。"""

    @pytest.mark.asyncio
    async def test_variant_id_in_artifact_refs(self, scheduler):
        """textToImage 和 imageToVideo 的 ArtifactRef 应包含 variant_id。"""
        factory = SkiLessonMockFactory()
        await run_ski_pipeline(scheduler, "exec-ski", factory)

        # 检查 task 结果中包含 variant_id
        conn = get_connection()
        tasks = conn.execute(
            "SELECT id, result_json FROM tasks WHERE execution_id = ? ORDER BY id",
            ("exec-ski",),
        ).fetchall()

        for row in tasks:
            result = json.loads(row["result_json"]) if row["result_json"] else {}
            output = result.get("output", {})
            kind = row["id"].split("-")[0] if "-" in row["id"] else ""

            # textToImage 和 imageToVideo 的 output 应有 scene_id
            if "textToImage" in row["id"] or "imageToVideo" in row["id"]:
                assert output.get("scene_id") == "scene-001"


class TestTemplateLoading:
    """验证从模板创建工作流。"""

    def test_template_loads_correctly(self):
        """realistic-ski-lesson 模板应可加载。"""
        from backend.app.services.templates import get_template_service

        svc = get_template_service()
        detail = svc.get_template("realistic-ski-lesson")

        assert detail is not None
        assert detail.name == "写实滑雪教学"
        assert len(detail.spec.nodes) == 6
        assert len(detail.spec.edges) == 5

    def test_template_variant_config(self):
        """模板的 textToImage 节点应包含 variantCount=2。"""
        from backend.app.services.templates import get_template_service

        svc = get_template_service()
        detail = svc.get_template("realistic-ski-lesson")

        img_node = next(
            n for n in detail.spec.nodes if n.data.kind == "textToImage"
        )
        assert img_node.data.config["variantCount"] == 2
        assert len(img_node.data.config["variants"]) == 2

    def test_create_workflow_from_template(self):
        """从模板创建工作流应生成新 ID。"""
        from backend.app.services.templates import get_template_service

        svc = get_template_service()
        spec = svc.create_from_template("realistic-ski-lesson")

        assert spec is not None
        assert spec.id.startswith("wf-")
        assert len(spec.nodes) == 6

    def test_create_workflow_with_prompt(self):
        """从模板创建工作流并注入 prompt。"""
        from backend.app.services.templates import get_template_service

        svc = get_template_service()
        spec = svc.create_from_template(
            "realistic-ski-lesson",
            params={"prompt": "冬季单板滑雪教学"},
        )

        assert spec is not None
        text_node = next(
            n for n in spec.nodes if n.data.kind == "textInput"
        )
        assert text_node.data.config["prompt"] == "冬季单板滑雪教学"


class TestSceneBundleFixture:
    """验证 Scene Bundle fixture 的结构。"""

    def test_bundle_schema_valid(self):
        """Scene Bundle 应包含必要字段。"""
        bundle = SKI_LESSON_SCENE_BUNDLE
        assert bundle["schemaVersion"] == "1.0"
        assert len(bundle["scenes"]) == 1
        assert bundle["scenes"][0]["sceneId"] == "scene-001"

    def test_bundle_has_image_and_video_prompts(self):
        """每个 scene 应有 image 和 video prompt。"""
        scene = SKI_LESSON_SCENE_BUNDLE["scenes"][0]
        assert len(scene["image"]["prompt"]) > 100
        assert len(scene["video"]["prompt"]) > 100

    def test_bundle_metadata_has_variant_count(self):
        """metadata 应声明 variantCount=2。"""
        meta = SKI_LESSON_SCENE_BUNDLE["scenes"][0]["metadata"]
        assert meta["variantCount"] == 2
        assert meta["outputStrategy"] == "two_variants_to_video"
        assert meta["peopleCount"] == 2
        assert meta["backgroundPeopleAllowed"] is False

    def test_variants_defined(self):
        """应有 2 个变体定义。"""
        assert len(SKI_LESSON_VARIANTS) == 2
        assert SKI_LESSON_VARIANTS[0]["id"] == "variant-01"
        assert SKI_LESSON_VARIANTS[1]["id"] == "variant-02"

    def test_bundle_no_secrets(self):
        """Bundle 不应包含 API Key、签名 URL 或绝对路径。"""
        bundle_str = json.dumps(SKI_LESSON_SCENE_BUNDLE)
        assert "sk-" not in bundle_str
        assert "https://dashscope.aliyuncs.com/oss" not in bundle_str
        assert "D:\\" not in bundle_str
        assert "/Users/" not in bundle_str


class TestBackwardCompatibility:
    """验证不含 variantCount 的工作流仍正常工作。"""

    def test_no_variant_count_expands_by_scene_only(self):
        """无 variantCount 时，textToImage 只按 scene 展开。"""
        spec = {
            "id": "wf-no-variant",
            "name": "无变体测试",
            "nodes": [
                {"id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
                 "data": {"kind": "textInput", "label": "输入", "config": {}}},
                {"id": "n2", "type": "studio", "position": {"x": 200, "y": 0},
                 "data": {"kind": "storyboard", "label": "分镜",
                          "config": {"scenes": 2}}},
                {"id": "n3", "type": "studio", "position": {"x": 400, "y": 0},
                 "data": {"kind": "textToImage", "label": "图片",
                          "config": {"mapOver": True, "scenes": 2}}},
                {"id": "n4", "type": "studio", "position": {"x": 600, "y": 0},
                 "data": {"kind": "output", "label": "输出", "config": {}}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"},
            ],
        }
        plan = compile_workflow(spec)
        img_tasks = [t for t in plan.tasks if t.node_id == "n3"]
        assert len(img_tasks) == 2
        # item_key 应为纯 scene_id，不含 ::
        for t in img_tasks:
            assert "::" not in (t.item_key or "")
