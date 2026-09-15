"""Tests for Agent preview and patch endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.providers import init_providers, clear_providers
from backend.app.handlers import init_mock_handlers


@pytest.fixture
def client():
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    with TestClient(app) as c:
        yield c
    clear_providers()


class TestAgentPreview:
    """Tests for Agent preview endpoints."""

    def test_generate_preview(self, client):
        """generate-preview returns spec without writing to DB."""
        response = client.post("/api/agent/generate-preview", json={"prompt": "自然风光视频"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "spec" in data
        assert data["destructive"] is False
        assert data["warnings"] == []
        spec = data["spec"]
        assert "nodes" in spec
        assert len(spec["nodes"]) > 0

    def test_generate_preview_empty_prompt(self, client):
        """generate-preview rejects empty prompt."""
        response = client.post("/api/agent/generate-preview", json={"prompt": ""})
        assert response.status_code == 422

    def test_modify_preview(self, client):
        """modify-preview returns patch with diff and warnings."""
        # First create a workflow via generate endpoint
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        response = client.post("/api/agent/modify-preview", json={
            "workflow_id": workflow_id,
            "instruction": "添加一个输出节点",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "patch" in data
        assert "diff" in data
        assert isinstance(data["warnings"], list)
        assert isinstance(data["destructive"], bool)

    def test_modify_preview_nonexistent_workflow(self, client):
        """modify-preview returns 404 for missing workflow."""
        response = client.post("/api/agent/modify-preview", json={
            "workflow_id": "nonexistent",
            "instruction": "test",
        })
        assert response.status_code == 404

    def test_apply_patch_with_expected_version(self, client):
        """apply-patch accepts expected_version and returns updated spec."""
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        response = client.post("/api/agent/apply-patch", json={
            "workflow_id": workflow_id,
            "patch": {
                "description": "空 patch 测试",
                "add_nodes": [],
                "remove_nodes": [],
                "update_nodes": [],
                "add_edges": [],
                "remove_edges": [],
            },
            "expected_version": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_apply_patch_version_conflict(self, client):
        """apply-patch returns 409 when expected_version mismatches."""
        gen_resp = client.post("/api/agent/generate", json={"prompt": "测试"})
        workflow_id = gen_resp.json()["id"]

        response = client.post("/api/agent/apply-patch", json={
            "workflow_id": workflow_id,
            "patch": {
                "description": "版本冲突测试",
                "add_nodes": [],
                "remove_nodes": [],
                "update_nodes": [],
                "add_edges": [],
                "remove_edges": [],
            },
            "expected_version": 999,
        })
        assert response.status_code == 409


class TestAgentDiffHelpers:
    """Tests for _generate_diff and _check_destructive helpers."""

    def test_generate_diff_add_nodes(self):
        """Diff shows added nodes."""
        from backend.app.api.agent import _generate_diff
        from backend.app.models import WorkflowSpec, GraphPatch, WorkflowNode, NodeData, Position

        spec = WorkflowSpec(id="wf-test", name="test", nodes=[], edges=[])
        patch = GraphPatch(
            description="add nodes",
            add_nodes=[
                WorkflowNode(
                    id="n1",
                    position=Position(x=0, y=0),
                    data=NodeData(label="Test Node", description="", kind="textInput"),
                ),
            ],
        )
        diff = _generate_diff(spec, patch)
        assert "新增 1 个节点" in diff
        assert "Test Node" in diff

    def test_generate_diff_no_changes(self):
        """Diff shows no-change message for empty patch."""
        from backend.app.api.agent import _generate_diff
        from backend.app.models import WorkflowSpec, GraphPatch

        spec = WorkflowSpec(id="wf-test", name="test", nodes=[], edges=[])
        patch = GraphPatch()
        diff = _generate_diff(spec, patch)
        assert "无变更" in diff

    def test_check_destructive_with_removes(self):
        """Warnings list removal operations."""
        from backend.app.api.agent import _check_destructive
        from backend.app.models import GraphPatch

        patch = GraphPatch(
            remove_nodes=["n1", "n2"],
            remove_edges=["e1"],
        )
        warnings = _check_destructive(patch)
        assert len(warnings) == 2
        assert any("节点" in w for w in warnings)
        assert any("连线" in w for w in warnings)

    def test_check_destructive_no_removes(self):
        """No warnings when patch has no removals."""
        from backend.app.api.agent import _check_destructive
        from backend.app.models import GraphPatch

        patch = GraphPatch()
        warnings = _check_destructive(patch)
        assert warnings == []
