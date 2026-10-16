"""Execution API 测试 — 启动执行、查询状态、取消。"""

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db
from backend.app.main import app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def managed_client():
    with client:
        yield

SAMPLE_SPEC = {
    "schemaVersion": "1.0",
    "id": "exec-api-test",
    "name": "执行 API 测试",
    "nodes": [
        {"id": "n1", "type": "studio", "position": {"x": 0, "y": 0},
         "data": {"label": "输入", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {"prompt": "测试"}}},
    ],
    "edges": [],
}


def _create_workflow() -> str:
    resp = client.post("/api/workflows", json=SAMPLE_SPEC)
    return resp.json()["id"]


class TestStartExecution:
    def test_start_execution(self):
        wf_id = _create_workflow()
        resp = client.post(f"/api/executions/{wf_id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "running"
        assert body["task_count"] > 0

    def test_start_nonexistent_workflow(self):
        resp = client.post("/api/executions/nonexistent/start")
        assert resp.status_code == 404

    def test_execution_rechecks_resource_limits_before_creating_record(self, monkeypatch):
        from backend.app.config import reset_settings
        from backend.app.db.connection import get_connection

        wf_id = _create_workflow()
        monkeypatch.setenv("AI_VIDEO_AGENT_MAX_NODES", "0")
        reset_settings()
        try:
            resp = client.post(f"/api/executions/{wf_id}/start")
            assert resp.status_code == 422
            assert resp.json()["detail"]["errors"][0]["code"] == "NODE_LIMIT_EXCEEDED"
            count = get_connection().execute(
                "SELECT COUNT(*) FROM executions WHERE workflow_id = ?", (wf_id,)
            ).fetchone()[0]
            assert count == 0
        finally:
            monkeypatch.delenv("AI_VIDEO_AGENT_MAX_NODES", raising=False)
            reset_settings()

    def test_module_effective_config_reaches_queued_task(self):
        spec = {
            "schemaVersion": "2.0",
            "manifestVersion": "1.0",
            "id": "exec-module-test",
            "name": "模块执行配置测试",
            "nodes": [
                {
                    "id": "input-1", "type": "studio", "position": {"x": 0, "y": 0},
                    "data": {"label": "输入", "description": "", "kind": "textInput", "status": "idle", "config": {"prompt": "test"}},
                },
                {
                    "id": "story-1", "type": "studio", "position": {"x": 200, "y": 0},
                    "data": {"label": "分镜", "description": "", "kind": "storyboard", "status": "idle", "config": {"scenes": 1}},
                },
                {
                    "id": "seedream-1", "type": "studio", "position": {"x": 400, "y": 0},
                    "data": {
                        "label": "Seedream", "description": "", "kind": "textToImage", "status": "idle",
                        "config": {},
                        "moduleId": "builtin.seedream.text-to-image",
                        "moduleVersion": "1.0.0",
                        "configOverrides": {"size": "1024x1024", "seed": 99},
                    },
                },
            ],
            "edges": [
                {"id": "e1", "source": "input-1", "sourceHandle": "text", "target": "story-1", "targetHandle": "prompt"},
                {"id": "e2", "source": "story-1", "sourceHandle": "scenes", "target": "seedream-1", "targetHandle": "scene"},
            ],
        }
        create = client.post("/api/workflows", json=spec)
        assert create.status_code == 201, create.text

        started = client.post("/api/executions/exec-module-test/start")
        assert started.status_code == 201, started.text
        tasks = client.get(f"/api/executions/{started.json()['id']}/tasks").json()
        image_tasks = [task for task in tasks if task["node_id"] == "seedream-1"]

        assert image_tasks
        assert image_tasks[0]["config"]["provider"] == "doubao"
        assert image_tasks[0]["config"]["size"] == "1024x1024"
        assert image_tasks[0]["config"]["seed"] == 99


class TestGetExecution:
    def test_get_execution(self):
        wf_id = _create_workflow()
        start_resp = client.post(f"/api/executions/{wf_id}/start")
        exec_id = start_resp.json()["id"]
        resp = client.get(f"/api/executions/{exec_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == exec_id

    def test_get_nonexistent_execution(self):
        resp = client.get("/api/executions/nonexistent")
        assert resp.status_code == 404


class TestGetExecutionTasks:
    def test_tasks_listed(self):
        wf_id = _create_workflow()
        start_resp = client.post(f"/api/executions/{wf_id}/start")
        exec_id = start_resp.json()["id"]
        resp = client.get(f"/api/executions/{exec_id}/tasks")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) > 0
        # 所有任务应为 pending
        assert all(t["status"] == "pending" for t in tasks)


class TestCancelExecution:
    def test_cancel(self):
        wf_id = _create_workflow()
        start_resp = client.post(f"/api/executions/{wf_id}/start")
        exec_id = start_resp.json()["id"]
        resp = client.post(f"/api/executions/{exec_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestExecutionEvents:
    def test_events_endpoint(self):
        wf_id = _create_workflow()
        start_resp = client.post(f"/api/executions/{wf_id}/start")
        exec_id = start_resp.json()["id"]
        resp = client.get(f"/api/executions/{exec_id}/events")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) > 0  # 至少有 execution.started 事件
