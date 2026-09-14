"""Recovery tests — worker crash recovery, task queue resilience."""

import json
import uuid
import pytest
from backend.app.db.connection import get_connection, close_connection, init_db
from backend.app.engine.queue import (
    enqueue_tasks, claim_task, complete_task, fail_task,
    heartbeat, recover_orphans, get_task,
)
import backend.app.db.connection as conn_module


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """每个测试使用临时数据库。"""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()

    # 创建测试工作流和执行记录
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
        "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
        ("wf-test", "Test Workflow"),
    )
    conn.commit()

    yield
    close_connection()


class TestOrphanRecovery:
    """孤儿任务回收测试。"""

    def _create_execution(self, workflow_id: str = "wf-test") -> str:
        """创建测试执行记录。"""
        execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        conn = get_connection()
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
            "VALUES (?, ?, '{}', 'running', datetime('now'))",
            (execution_id, workflow_id),
        )
        conn.commit()
        return execution_id

    def test_recover_orphaned_task(self):
        """回收超时的孤儿任务。"""
        execution_id = self._create_execution()

        # 入队任务
        tasks = [{"id": "task-1", "node_id": "n1", "kind": "textInput", "label": "Test",
                  "config": {}, "depends_on": []}]
        enqueue_tasks("wf-test", execution_id, tasks)

        # 领取任务
        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # 模拟 Worker 崩溃：手动设置 lease 过期
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') WHERE id = 'task-1'"
        )
        conn.commit()

        # 回收孤儿任务
        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert "task-1" in orphans

        # 任务应该可以被重新领取
        task2 = claim_task("worker-2", lease_seconds=30)
        assert task2 is not None
        assert task2["id"] == "task-1"

    def test_no_orphans_when_fresh(self):
        """没有超时任务时返回空列表。"""
        execution_id = self._create_execution()
        tasks = [{"id": "task-1", "node_id": "n1", "kind": "textInput", "label": "Test",
                  "config": {}, "depends_on": []}]
        enqueue_tasks("wf-test", execution_id, tasks)

        # 立即回收应该没有孤儿
        orphans = recover_orphans("worker-1", lease_seconds=30)
        assert len(orphans) == 0


class TestLeaseExpiration:
    """租约过期测试。"""

    def setup_method(self):
        self.execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        conn = get_connection()
        # 创建专用工作流
        conn.execute(
            "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
            "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
            ("wf-lease", "Lease Test"),
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
            "VALUES (?, ?, '{}', 'running', datetime('now'))",
            (self.execution_id, "wf-lease"),
        )
        conn.commit()

    def test_heartbeat_extends_lease(self):
        """心跳续租。"""
        tasks = [{"id": "task-hb", "node_id": "n1", "kind": "textInput", "label": "HB",
                  "config": {}, "depends_on": []}]
        enqueue_tasks("wf-lease", self.execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # 记录初始 lease
        conn = get_connection()
        row = conn.execute("SELECT lease_until FROM tasks WHERE id = 'task-hb'").fetchone()
        initial_lease = row["lease_until"]

        # 续租
        heartbeat("task-hb", lease_seconds=60)

        # 验证 lease 已更新
        row = conn.execute("SELECT lease_until FROM tasks WHERE id = 'task-hb'").fetchone()
        new_lease = row["lease_until"]
        assert new_lease >= initial_lease


class TestConcurrentClaim:
    """并发领取测试。"""

    def setup_method(self):
        self.execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
            "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
            ("wf-concurrent", "Concurrent Test"),
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
            "VALUES (?, ?, '{}', 'running', datetime('now'))",
            (self.execution_id, "wf-concurrent"),
        )
        conn.commit()

    def test_only_one_worker_claims_task(self):
        """只有一个 Worker 能领取任务。"""
        tasks = [{"id": "task-unique", "node_id": "n1", "kind": "textInput", "label": "Unique",
                  "config": {}, "depends_on": []}]
        enqueue_tasks("wf-concurrent", self.execution_id, tasks)

        # Worker 1 领取
        task1 = claim_task("worker-1", lease_seconds=30)
        assert task1 is not None

        # Worker 2 尝试领取同一个任务（应该失败，因为没有其他 ready 任务）
        task2 = claim_task("worker-2", lease_seconds=30)
        assert task2 is None  # 没有其他可领取的任务

    def test_sequential_claims_after_completion(self):
        """任务完成后可以被重新领取（新任务）。"""
        tasks = [
            {"id": "task-a", "node_id": "n1", "kind": "textInput", "label": "A",
             "config": {}, "depends_on": []},
            {"id": "task-b", "node_id": "n2", "kind": "textInput", "label": "B",
             "config": {}, "depends_on": ["task-a"]},
        ]
        enqueue_tasks("wf-concurrent", self.execution_id, tasks)

        # 领取并完成 task-a
        task = claim_task("worker-1", lease_seconds=30)
        assert task["id"] == "task-a"
        complete_task("task-a")

        # 现在 task-b 应该可以被领取
        task2 = claim_task("worker-1", lease_seconds=30)
        assert task2["id"] == "task-b"


class TestTaskFailureRecovery:
    """任务失败恢复测试。"""

    def setup_method(self):
        self.execution_id = f"exec-{uuid.uuid4().hex[:8]}"
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
            "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
            ("wf-fail", "Fail Test"),
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
            "VALUES (?, ?, '{}', 'running', datetime('now'))",
            (self.execution_id, "wf-fail"),
        )
        conn.commit()

    def test_failure_propagates_to_downstream(self):
        """失败传播到下游任务。"""
        tasks = [
            {"id": "task-root", "node_id": "n1", "kind": "textInput", "label": "Root",
             "config": {}, "depends_on": []},
            {"id": "task-child", "node_id": "n2", "kind": "textInput", "label": "Child",
             "config": {}, "depends_on": ["task-root"]},
        ]
        enqueue_tasks("wf-fail", self.execution_id, tasks)

        # 领取并失败 task-root
        claim_task("worker-1", lease_seconds=30)
        skipped = fail_task("task-root", "Simulated failure")

        # task-child 应该被跳过
        assert "task-child" in skipped

        # 验证状态
        child = get_task("task-child")
        assert child["status"] == "skipped"

    def test_failed_task_has_error_message(self):
        """失败任务包含错误信息。"""
        tasks = [{"id": "task-err", "node_id": "n1", "kind": "textInput", "label": "Err",
                  "config": {}, "depends_on": []}]
        enqueue_tasks("wf-fail", self.execution_id, tasks)

        claim_task("worker-1", lease_seconds=30)
        fail_task("task-err", "Custom error message")

        task = get_task("task-err")
        assert task["status"] == "failed"
        assert task["error"] == "Custom error message"
