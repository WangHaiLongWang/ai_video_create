"""API 端点测试。"""

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db
from backend.app.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    from backend.app.providers import init_providers, clear_providers
    from backend.app.handlers import init_mock_handlers

    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    clear_providers()
    init_providers(mock=True)
    init_mock_handlers()
    yield
    close_connection()
    clear_providers()


client = TestClient(app)

SAMPLE_SPEC = {
    "schemaVersion": "1.0",
    "id": "api-test-1",
    "name": "API 测试工作流",
    "nodes": [
        {
            "id": "n1",
            "type": "studio",
            "position": {"x": 0, "y": 0},
            "data": {"label": "输入", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {"prompt": "测试"}},
        }
    ],
    "edges": [],
}


class TestHealth:
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAgentGenerate:
    def test_agent_generates_typed_workflow(self):
        response = client.post("/api/agent/generate", json={"prompt": "创建一个 7 镜头短视频"})
        assert response.status_code == 200
        body = response.json()
        assert len(body["nodes"]) == 6
        assert len(body["edges"]) == 5
        storyboard = next(node for node in body["nodes"] if node["data"]["kind"] == "storyboard")
        assert storyboard["data"]["config"]["scenes"] == 7


class TestWorkflowCRUD:
    def test_list_empty(self):
        response = client.get("/api/workflows")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_workflow(self):
        response = client.post("/api/workflows", json=SAMPLE_SPEC)
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "api-test-1"
        assert body["version"] == 1

    def test_get_workflow(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        response = client.get("/api/workflows/api-test-1")
        assert response.status_code == 200
        body = response.json()
        assert body["spec"]["nodes"][0]["data"]["kind"] == "textInput"

    def test_get_nonexistent(self):
        response = client.get("/api/workflows/nonexistent")
        assert response.status_code == 404

    def test_update_workflow(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        updated = {**SAMPLE_SPEC, "name": "已更新"}
        response = client.put("/api/workflows/api-test-1", json={"spec": updated, "expected_version": 1})
        assert response.status_code == 200
        assert response.json()["version"] == 2

    def test_update_version_conflict(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        response = client.put("/api/workflows/api-test-1", json={"spec": SAMPLE_SPEC, "expected_version": 99})
        assert response.status_code == 409

    def test_delete_workflow(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        response = client.delete("/api/workflows/api-test-1")
        assert response.status_code == 204
        response = client.get("/api/workflows/api-test-1")
        assert response.status_code == 404

    def test_duplicate_workflow(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        response = client.post("/api/workflows/api-test-1/duplicate")
        assert response.status_code == 201
        body = response.json()
        assert body["id"] != "api-test-1"
        assert "副本" in body["name"]

    def test_export_workflow(self):
        client.post("/api/workflows", json=SAMPLE_SPEC)
        response = client.post("/api/workflows/api-test-1/export")
        assert response.status_code == 200
        assert "spec" in response.json()

    def test_import_workflow(self):
        response = client.post("/api/workflows/import", json=SAMPLE_SPEC)
        assert response.status_code == 201
