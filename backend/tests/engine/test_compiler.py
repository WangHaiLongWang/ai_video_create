"""Graph Compiler 测试 — 拓扑排序、map 展开、失败传播。"""

import pytest
from backend.app.engine.compiler import (
    compile_workflow, topological_sort, CompileError, ExecutionPlan, Task,
)


def _linear_spec(scene_count: int = 3) -> dict:
    """构建标准线性管道工作流。"""
    return {
        "schemaVersion": "1.0",
        "id": "test-pipeline",
        "name": "测试管道",
        "nodes": [
            {"id": "textInput-1", "type": "studio", "position": {"x": 0, "y": 0},
             "data": {"label": "输入", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {"prompt": "测试"}}},
            {"id": "storyboard-1", "type": "studio", "position": {"x": 300, "y": 0},
             "data": {"label": "分镜", "description": "", "kind": "storyboard", "inputType": "text", "outputType": "list<scene>", "status": "idle", "config": {"provider": "Mock", "scenes": scene_count}}},
            {"id": "textToImage-1", "type": "studio", "position": {"x": 600, "y": 0},
             "data": {"label": "文生图", "description": "", "kind": "textToImage", "inputType": "list<scene>", "outputType": "list<image>", "status": "idle", "config": {"provider": "Mock", "mapOver": True}}},
            {"id": "imageToVideo-1", "type": "studio", "position": {"x": 900, "y": 0},
             "data": {"label": "图生视频", "description": "", "kind": "imageToVideo", "inputType": "list<image>", "outputType": "list<video>", "status": "idle", "config": {"provider": "Mock", "duration": 4, "mapOver": True}}},
            {"id": "videoConcat-1", "type": "studio", "position": {"x": 1200, "y": 0},
             "data": {"label": "合成", "description": "", "kind": "videoConcat", "inputType": "list<video>", "outputType": "video", "status": "idle", "config": {"transition": "crossfade"}}},
            {"id": "output-1", "type": "studio", "position": {"x": 1500, "y": 0},
             "data": {"label": "输出", "description": "", "kind": "output", "inputType": "video", "status": "idle", "config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "textInput-1", "target": "storyboard-1", "type": "smoothstep"},
            {"id": "e2", "source": "storyboard-1", "target": "textToImage-1", "type": "smoothstep"},
            {"id": "e3", "source": "textToImage-1", "target": "imageToVideo-1", "type": "smoothstep"},
            {"id": "e4", "source": "imageToVideo-1", "target": "videoConcat-1", "type": "smoothstep"},
            {"id": "e5", "source": "videoConcat-1", "target": "output-1", "type": "smoothstep"},
        ],
    }


class TestTopologicalSort:
    def test_linear_graph(self):
        spec = _linear_spec()
        sorted_nodes = topological_sort(spec["nodes"], spec["edges"])
        assert [n["id"] for n in sorted_nodes] == [
            "textInput-1", "storyboard-1", "textToImage-1",
            "imageToVideo-1", "videoConcat-1", "output-1",
        ]

    def test_diamond_graph(self):
        nodes = [
            {"id": "a", "data": {}},
            {"id": "b", "data": {}},
            {"id": "c", "data": {}},
            {"id": "d", "data": {}},
        ]
        edges = [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "a", "target": "c"},
            {"id": "e3", "source": "b", "target": "d"},
            {"id": "e4", "source": "c", "target": "d"},
        ]
        sorted_nodes = topological_sort(nodes, edges)
        assert len(sorted_nodes) == 4
        # a 必须在 b、c 之前；b、c 必须在 d 之前
        ids = [n["id"] for n in sorted_nodes]
        assert ids.index("a") < ids.index("b")
        assert ids.index("a") < ids.index("c")
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")

    def test_cyclic_graph_raises(self):
        nodes = [{"id": "a", "data": {}}, {"id": "b", "data": {}}]
        edges = [
            {"id": "e1", "source": "a", "target": "b"},
            {"id": "e2", "source": "b", "target": "a"},
        ]
        with pytest.raises(CompileError, match="环形依赖"):
            topological_sort(nodes, edges)

    def test_dangling_edge_raises(self):
        nodes = [{"id": "a", "data": {}}]
        edges = [{"id": "e1", "source": "a", "target": "ghost"}]
        with pytest.raises(CompileError, match="不存在的节点"):
            topological_sort(nodes, edges)


class TestCompileWorkflow:
    def test_linear_pipeline_task_count(self):
        plan = compile_workflow(_linear_spec(scene_count=3))
        # textInput(1) + storyboard(1) + textToImage(3 map) + imageToVideo(3 map) + videoConcat(1) + output(1) = 10
        assert len(plan.tasks) == 10

    def test_map_expansion_creates_per_scene_tasks(self):
        plan = compile_workflow(_linear_spec(scene_count=5))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        vid_tasks = [t for t in plan.tasks if t.node_kind == "imageToVideo"]
        assert len(img_tasks) == 5
        assert len(vid_tasks) == 5
        # 每个任务有唯一的 item_key
        assert len(set(t.item_key for t in img_tasks)) == 5

    def test_dependencies_are_correct(self):
        plan = compile_workflow(_linear_spec(scene_count=2))
        # storyboard task 依赖 textInput
        storyboard = next(t for t in plan.tasks if t.node_kind == "storyboard")
        assert len(storyboard.depends_on) == 1
        assert "textInput-1" in storyboard.depends_on[0]

    def test_map_tasks_depend_on_upstream(self):
        plan = compile_workflow(_linear_spec(scene_count=2))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        # 每个 textToImage 任务依赖 storyboard 任务
        for t in img_tasks:
            assert any("storyboard" in dep for dep in t.depends_on)

    def test_execution_plan_summary(self):
        plan = compile_workflow(_linear_spec(scene_count=3))
        summary = plan.summary()
        assert summary["total"] == 10
        assert summary.get("pending", 0) == 10

    def test_empty_workflow_raises(self):
        with pytest.raises(CompileError, match="没有任何节点"):
            compile_workflow({"nodes": [], "edges": [], "id": "empty", "name": "空"})


class TestExecutionPlan:
    def test_get_ready_tasks_initial(self):
        plan = compile_workflow(_linear_spec(scene_count=2))
        ready = plan.get_ready_tasks()
        # 只有 textInput 没有依赖，是初始就绪的
        assert len(ready) == 1
        assert ready[0].node_kind == "textInput"

    def test_mark_failed_propagates(self):
        plan = compile_workflow(_linear_spec(scene_count=2))
        # 完成 textInput
        ti = next(t for t in plan.tasks if t.node_kind == "textInput")
        ti.status = "completed"
        # 故意把 storyboard 的 status 设为 pending
        sb = next(t for t in plan.tasks if t.node_kind == "storyboard")
        sb.status = "pending"
        # 标记 storyboard 失败
        affected = plan.mark_failed(sb.id)
        # 所有下游应该被 skipped
        assert len(affected) > 0
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        for t in img_tasks:
            assert t.status == "skipped"

    def test_is_complete(self):
        plan = compile_workflow(_linear_spec(scene_count=2))
        assert not plan.is_complete()
        for t in plan.tasks:
            t.status = "completed"
        assert plan.is_complete()


# ------------------------------------------------------------------
#  Variant fan-out edge cases (SKI-003)
# ------------------------------------------------------------------

def _variant_spec(variant_count: int = 1, variants: list | None = None, scene_count: int = 1) -> dict:
    """Build a minimal workflow with a textToImage node carrying variantCount."""
    cfg: dict = {"mapOver": True, "variantCount": variant_count}
    if variants is not None:
        cfg["variants"] = variants
    return {
        "id": "variant-test",
        "name": "Variant Test",
        "nodes": [
            {"id": "sb", "type": "studio", "position": {"x": 0, "y": 0},
             "data": {"kind": "storyboard", "label": "SB", "config": {"scenes": scene_count}}},
            {"id": "t2i", "type": "studio", "position": {"x": 300, "y": 0},
             "data": {"kind": "textToImage", "label": "T2I", "config": cfg}},
        ],
        "edges": [
            {"id": "e1", "source": "sb", "target": "t2i", "type": "smoothstep"},
        ],
    }


class TestVariantFanOutEdgeCases:
    """Edge cases for variantCount/variant fan-out (SKI-003)."""

    def test_variant_count_0_creates_single_task(self):
        """variantCount=0 behaves like variantCount=1 (no fan-out, 1 task per scene)."""
        plan = compile_workflow(_variant_spec(variant_count=0))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 1
        # No variant fan-out when variantCount <= 1
        assert "::" not in (img_tasks[0].item_key or "")

    def test_variant_count_1_creates_single_task(self):
        """variantCount=1 (default) should produce exactly 1 task per scene, no fan-out."""
        plan = compile_workflow(_variant_spec(variant_count=1))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 1
        assert img_tasks[0].item_key == "scene-001"
        assert "::" not in (img_tasks[0].item_key or "")

    def test_variant_count_2_creates_two_tasks(self):
        """variantCount=2 should create 2 tasks with variant-01, variant-02."""
        plan = compile_workflow(_variant_spec(variant_count=2))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 2
        keys = sorted(t.item_key for t in img_tasks)
        assert keys == ["scene-001::variant-01", "scene-001::variant-02"]

    def test_variant_count_5_creates_five_tasks(self):
        """variantCount=5 should create 5 tasks with variant-01 through variant-05."""
        plan = compile_workflow(_variant_spec(variant_count=5))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 5
        keys = sorted(t.item_key for t in img_tasks)
        expected = [f"scene-001::variant-{i:02d}" for i in range(1, 6)]
        assert keys == expected

    def test_variant_count_not_set_defaults_to_1(self):
        """When variantCount is absent, it defaults to 1 (no fan-out)."""
        plan = compile_workflow(_variant_spec())  # variant_count=1 by default
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 1

    def test_empty_variants_list_defaults_prompt_suffix(self):
        """When variants list is empty, prompt suffix defaults to empty string."""
        plan = compile_workflow(_variant_spec(variant_count=2, variants=[]))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        for t in img_tasks:
            assert t.config.get("variant_prompt_suffix", "") == ""

    def test_missing_variants_key_defaults_prompt_suffix(self):
        """When variants key is absent from config, prompt suffix defaults to empty string."""
        plan = compile_workflow(_variant_spec(variant_count=2))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        for t in img_tasks:
            assert t.config.get("variant_prompt_suffix", "") == ""

    def test_missing_prompt_suffix_defaults_to_empty_string(self):
        """When a variant entry lacks promptSuffix, it defaults to empty string."""
        variants = [
            {"id": "variant-01"},  # no promptSuffix
            {"id": "variant-02", "promptSuffix": "something"},
        ]
        plan = compile_workflow(_variant_spec(variant_count=2, variants=variants))
        img_tasks = sorted(
            [t for t in plan.tasks if t.node_kind == "textToImage"],
            key=lambda t: t.config.get("variant_index", 0),
        )
        assert img_tasks[0].config.get("variant_prompt_suffix", "") == ""
        assert img_tasks[1].config.get("variant_prompt_suffix", "") == "something"

    def test_variant_index_stability_sorted_by_variant_id(self):
        """Variant tasks should be sorted by variant index (0-based) in stable order."""
        plan = compile_workflow(_variant_spec(variant_count=3))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        indices = [t.config.get("variant_index", 0) for t in img_tasks]
        assert indices == [0, 1, 2]

    def test_variant_ids_are_zero_padded(self):
        """Variant IDs should be zero-padded: variant-01, variant-02, ..., variant-10."""
        plan = compile_workflow(_variant_spec(variant_count=10))
        img_tasks = sorted(
            [t for t in plan.tasks if t.node_kind == "textToImage"],
            key=lambda t: t.config.get("variant_index", 0),
        )
        for i, t in enumerate(img_tasks):
            assert t.config["variant_id"] == f"variant-{i + 1:02d}"

    def test_multiple_scenes_x_variants(self):
        """variantCount fans out per-scene: 3 scenes x 2 variants = 6 tasks."""
        plan = compile_workflow(_variant_spec(variant_count=2, scene_count=3))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        assert len(img_tasks) == 6
        keys = sorted(t.item_key for t in img_tasks)
        expected = []
        for s in range(1, 4):
            for v in range(1, 3):
                expected.append(f"scene-{s:03d}::variant-{v:02d}")
        assert keys == expected

    def test_variant_task_depends_on_upstream(self):
        """All variant tasks should depend on the storyboard task."""
        plan = compile_workflow(_variant_spec(variant_count=3))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        for t in img_tasks:
            assert any("sb" in dep for dep in t.depends_on)

    def test_variant_tasks_are_marked_as_map_expansion(self):
        """All variant-expanded tasks should have is_map_expansion=True."""
        plan = compile_workflow(_variant_spec(variant_count=4))
        img_tasks = [t for t in plan.tasks if t.node_kind == "textToImage"]
        for t in img_tasks:
            assert t.is_map_expansion is True

    def test_variant_config_includes_scene_and_variant_metadata(self):
        """Each variant task config should include scene_id, variant_id, variant_index."""
        plan = compile_workflow(_variant_spec(variant_count=2))
        img_tasks = sorted(
            [t for t in plan.tasks if t.node_kind == "textToImage"],
            key=lambda t: t.config.get("variant_index", 0),
        )
        for t in img_tasks:
            assert "scene_id" in t.config
            assert "variant_id" in t.config
            assert "variant_index" in t.config
        assert img_tasks[0].config["scene_id"] == "scene-001"
        assert img_tasks[0].config["variant_id"] == "variant-01"
        assert img_tasks[0].config["variant_index"] == 0
