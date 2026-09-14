"""工作流校验边界测试 — 覆盖各种非法输入。"""

import pytest
from pydantic import ValidationError

from backend.app.models import WorkflowSpec


def _make_spec(nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "schemaVersion": "1.0",
        "id": "test-wf",
        "name": "测试工作流",
        "nodes": nodes,
        "edges": edges,
    }


NODE_A = {
    "id": "a",
    "type": "studio",
    "position": {"x": 0, "y": 0},
    "data": {"label": "A", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {}},
}
NODE_B = {
    "id": "b",
    "type": "studio",
    "position": {"x": 100, "y": 0},
    "data": {"label": "B", "description": "", "kind": "storyboard", "inputType": "text", "outputType": "list<scene>", "status": "idle", "config": {}},
}
NODE_C = {
    "id": "c",
    "type": "studio",
    "position": {"x": 200, "y": 0},
    "data": {"label": "C", "description": "", "kind": "textToImage", "inputType": "list<scene>", "outputType": "list<image>", "status": "idle", "config": {}},
}
# 端口不兼容的节点：inputType 不匹配 A 的 outputType
NODE_D_INCOMPAT = {
    "id": "d",
    "type": "studio",
    "position": {"x": 300, "y": 0},
    "data": {"label": "D", "description": "", "kind": "imageToVideo", "inputType": "list<image>", "outputType": "list<video>", "status": "idle", "config": {}},
}


class TestDuplicateNodeIds:
    def test_rejects_duplicate_ids(self):
        dup_node = {**NODE_A, "id": "dup"}
        dup_node2 = {**NODE_B, "id": "dup"}
        spec = _make_spec([dup_node, dup_node2], [])
        with pytest.raises(ValidationError, match="节点 ID 必须唯一"):
            WorkflowSpec(**spec)


class TestDanglingEdges:
    def test_rejects_edge_to_unknown_node(self):
        spec = _make_spec(
            [NODE_A],
            [{"id": "e1", "source": "a", "target": "nonexistent", "type": "smoothstep"}],
        )
        with pytest.raises(ValidationError, match="引用了不存在的节点"):
            WorkflowSpec(**spec)

    def test_rejects_edge_from_unknown_node(self):
        spec = _make_spec(
            [NODE_A],
            [{"id": "e1", "source": "ghost", "target": "a", "type": "smoothstep"}],
        )
        with pytest.raises(ValidationError, match="引用了不存在的节点"):
            WorkflowSpec(**spec)


class TestPortTypeCompatibility:
    def test_rejects_incompatible_port_types(self):
        # textInput(outputType=text) -> imageToVideo(inputType=list<image>) 不兼容
        spec = _make_spec(
            [NODE_A, NODE_D_INCOMPAT],
            [{"id": "e1", "source": "a", "target": "d", "type": "smoothstep"}],
        )
        with pytest.raises(ValidationError, match="端口类型不兼容"):
            WorkflowSpec(**spec)

    def test_accepts_compatible_port_types(self):
        # textInput(outputType=text) -> storyboard(inputType=text) 兼容
        spec = _make_spec(
            [NODE_A, NODE_B],
            [{"id": "e1", "source": "a", "target": "b", "type": "smoothstep"}],
        )
        wf = WorkflowSpec(**spec)
        assert len(wf.nodes) == 2
        assert len(wf.edges) == 1


class TestValidWorkflow:
    def test_full_pipeline_is_valid(self):
        spec = _make_spec(
            [NODE_A, NODE_B, NODE_C],
            [
                {"id": "e1", "source": "a", "target": "b", "type": "smoothstep"},
                {"id": "e2", "source": "b", "target": "c", "type": "smoothstep"},
            ],
        )
        wf = WorkflowSpec(**spec)
        assert wf.schemaVersion == "1.0"
        assert len(wf.nodes) == 3
        assert len(wf.edges) == 2

    def test_empty_edges_valid(self):
        spec = _make_spec([NODE_A], [])
        wf = WorkflowSpec(**spec)
        assert len(wf.nodes) == 1
        assert len(wf.edges) == 0
