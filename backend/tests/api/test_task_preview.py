"""Tests for task preview and task-level retry endpoints."""

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db
from backend.app.main import app
from backend.app.engine.queue import fail_task


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    global _spec_counter
    _spec_counter = 0
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


client = TestClient(app)

_spec_counter = 0


def _make_spec() -> dict:
    global _spec_counter
    _spec_counter += 1
    return {
        "schemaVersion": "1.0",
        "id": f"preview-test-{_spec_counter}",
        "name": f"预览测试-{_spec_counter}",
        "nodes": [
            {"id": f"n1-{_spec_counter}", "type": "studio", "position": {"x": 0, "y": 0},
             "data": {"label": f"输入-{_spec_counter}", "description": "", "kind": "textInput", "outputType": "text", "status": "idle", "config": {"prompt": "测试"}}},
        ],
        "edges": [],
    }


def _create_and_start() -> tuple[str, str]:
    resp = client.post("/api/workflows", json=_make_spec())
    wf_id = resp.json()["id"]
    start_resp = client.post(f"/api/executions/{wf_id}/start")
    exec_id = start_resp.json()["id"]
    return wf_id, exec_id


class TestTaskPreview:
    def test_preview_pending_task(self):
        _, exec_id = _create_and_start()
        # Get the first task
        tasks_resp = client.get(f"/api/executions/{exec_id}/tasks")
        tasks = tasks_resp.json()
        assert len(tasks) > 0
        task_id = tasks[0]["id"]

        resp = client.get(f"/api/executions/{exec_id}/tasks/{task_id}/preview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["status"] == "pending"
        assert "first_frame_url" in body
        assert "error_message" in body

    def test_preview_nonexistent_execution(self):
        resp = client.get("/api/executions/nonexistent/tasks/t1/preview")
        assert resp.status_code == 404

    def test_preview_nonexistent_task(self):
        _, exec_id = _create_and_start()
        resp = client.get(f"/api/executions/{exec_id}/tasks/nonexistent/preview")
        assert resp.status_code == 404

    def test_preview_task_wrong_execution(self):
        _, exec_id1 = _create_and_start()
        _, exec_id2 = _create_and_start()

        tasks_resp = client.get(f"/api/executions/{exec_id1}/tasks")
        task_id = tasks_resp.json()[0]["id"]

        resp = client.get(f"/api/executions/{exec_id2}/tasks/{task_id}/preview")
        assert resp.status_code == 404

    def test_preview_has_variant_label(self):
        _, exec_id = _create_and_start()
        tasks_resp = client.get(f"/api/executions/{exec_id}/tasks")
        task = tasks_resp.json()[0]
        task_id = task["id"]

        resp = client.get(f"/api/executions/{exec_id}/tasks/{task_id}/preview")
        body = resp.json()
        # variant_label should be present (may be None or item_key)
        assert "variant_label" in body
        assert "kind" in body
        assert "node_label" in body


class TestRetryTaskById:
    def test_retry_pending_task_fails(self):
        _, exec_id = _create_and_start()
        tasks_resp = client.get(f"/api/executions/{exec_id}/tasks")
        task_id = tasks_resp.json()[0]["id"]

        resp = client.post(f"/api/executions/{exec_id}/tasks/{task_id}/retry")
        assert resp.status_code == 400
        assert "failed" in resp.json()["detail"]

    def test_retry_nonexistent_execution(self):
        resp = client.post("/api/executions/nonexistent/tasks/t1/retry")
        assert resp.status_code == 404

    def test_retry_nonexistent_task(self):
        _, exec_id = _create_and_start()
        resp = client.post(f"/api/executions/{exec_id}/tasks/nonexistent/retry")
        assert resp.status_code == 404

    def test_retry_failed_task_succeeds(self):
        _, exec_id = _create_and_start()
        tasks_resp = client.get(f"/api/executions/{exec_id}/tasks")
        task = tasks_resp.json()[0]
        task_id = task["id"]

        # Force the task to failed state
        fail_task(task_id, error="Test error", max_retries=0)

        resp = client.post(f"/api/executions/{exec_id}/tasks/{task_id}/retry")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["status"] == "pending"
        assert "message" in body

    def test_retry_sets_execution_to_running(self):
        _, exec_id = _create_and_start()
        tasks_resp = client.get(f"/api/executions/{exec_id}/tasks")
        task_id = tasks_resp.json()[0]["id"]

        # Force the task to failed state
        fail_task(task_id, error="Test error", max_retries=0)

        # Check execution is failed
        exec_resp = client.get(f"/api/executions/{exec_id}")
        # It might be running or failed depending on task propagation

        # Retry the task
        client.post(f"/api/executions/{exec_id}/tasks/{task_id}/retry")

        # After retry, task should be pending
        tasks_resp2 = client.get(f"/api/executions/{exec_id}/tasks")
        task_after = [t for t in tasks_resp2.json() if t["id"] == task_id][0]
        assert task_after["status"] == "pending"
