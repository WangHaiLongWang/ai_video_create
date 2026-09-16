"""单节点重试 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, init_db, get_connection
from backend.app.main import app
from backend.app.engine.queue import (
    enqueue_tasks,
    claim_task,
    fail_task,
    complete_task,
    retry_node_task,
    DuplicateRetryError,
)


# ======================================================================
#  Fixtures
# ======================================================================

WORKFLOW_ID = "wf-api-retry-test"
EXECUTION_ID = "exec-api-retry-test"
NODE_ID = "n1"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test_retry_api.db")
    close_connection()
    init_db()

    # 创建测试 workflow + execution 记录
    conn = get_connection()
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        (WORKFLOW_ID, "API 重试测试工作流", "{}"),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        (EXECUTION_ID, WORKFLOW_ID, "{}", "running"),
    )
    conn.commit()

    yield
    close_connection()


@pytest.fixture
def client():
    """创建测试客户端。"""
    with TestClient(app) as c:
        yield c


def _setup_failed_node():
    """辅助函数：创建任务并使其失败（直接失败，不自动重试）。"""
    enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
        {"id": "t1", "node_id": NODE_ID, "kind": "textInput", "label": "输入",
         "config": {}, "depends_on": []},
    ])
    claim_task("worker-1")
    fail_task("t1", "执行失败", max_retries=1)


# ======================================================================
#  1. 重试失败节点
# ======================================================================

class TestRetryFailedNode:
    """重试失败节点测试。"""

    def test_retry_failed_node_success(self, client):
        """重试失败的节点 -> 200。"""
        _setup_failed_node()

        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["node_id"] == NODE_ID
        assert data["execution_id"] == EXECUTION_ID

    def test_retry_returns_task_info(self, client):
        """重试响应包含任务详情。"""
        _setup_failed_node()

        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == "t1"


# ======================================================================
#  2. 幂等键去重
# ======================================================================

class TestIdempotencyDedup:
    """幂等键去重测试。"""

    def test_retry_with_idempotency_key(self, client):
        """带幂等键的重试 -> 成功。"""
        _setup_failed_node()

        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID, "idempotency_key": "idem-api-001"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["idempotency_key"] == "idem-api-001"

    def test_duplicate_idempotency_key_conflict(self, client):
        """重复幂等键 -> 409 Conflict。"""
        _setup_failed_node()

        # 第一次重试 -> 任务回到 pending（幂等键已设置）
        client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID, "idempotency_key": "idem-api-002"},
        )

        # 相同幂等键再次重试 -> 409（任务仍处于 pending 状态）
        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID, "idempotency_key": "idem-api-002"},
        )
        assert response.status_code == 409
        assert "幂等键" in response.json()["detail"]


# ======================================================================
#  3. 重试非失败节点 (400)
# ======================================================================

class TestRetryNonFailedNode:
    """重试非失败节点测试。"""

    def test_retry_completed_node_returns_400(self, client):
        """重试已完成的节点 -> 400。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": NODE_ID, "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])
        claim_task("worker-1")
        complete_task("t1")

        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID},
        )
        assert response.status_code == 400
        assert "failed" in response.json()["detail"]

    def test_retry_pending_node_returns_400(self, client):
        """重试 pending 状态的节点 -> 400。"""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, [
            {"id": "t1", "node_id": NODE_ID, "kind": "textInput", "label": "输入",
             "config": {}, "depends_on": []},
        ])

        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": NODE_ID},
        )
        assert response.status_code == 400


# ======================================================================
#  4. 重试不存在的节点 (404)
# ======================================================================

class TestRetryNonexistentNode:
    """重试不存在的节点测试。"""

    def test_retry_nonexistent_node_returns_400(self, client):
        """重试不存在的节点 -> 400。"""
        response = client.post(
            f"/api/executions/{EXECUTION_ID}/retry",
            json={"node_id": "nonexistent-node"},
        )
        assert response.status_code == 400
        assert "不存在" in response.json()["detail"]

    def test_retry_on_nonexistent_execution_returns_404(self, client):
        """对不存在的执行重试 -> 404。"""
        response = client.post(
            "/api/executions/nonexistent-exec/retry",
            json={"node_id": NODE_ID},
        )
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]
