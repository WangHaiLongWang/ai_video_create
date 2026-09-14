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
