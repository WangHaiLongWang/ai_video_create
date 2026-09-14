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
