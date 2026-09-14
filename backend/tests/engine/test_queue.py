"""Task queue 测试 — 入队、领取、完成、失败传播、回收。"""

import pytest
from backend.app.db.connection import close_connection, init_db
from backend.app.engine.queue import (
    enqueue_tasks, claim_task, complete_task, fail_task,
    cancel_task, recover_orphans, get_task, get_tasks_by_execution,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    # 创建测试 workflow + execution 记录
    from backend.app.db.connection import get_connection
    conn = get_connection()
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        ("wf-test", "测试工作流", "{}"),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) VALUES (?, ?, ?, ?)",
        ("exec-test", "wf-test", "{}", "running"),
    )
    conn.commit()
    yield
    close_connection()


SAMPLE_TASKS = [
    {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入", "config": {}, "depends_on": []},
    {"id": "t2", "node_id": "n2", "kind": "storyboard", "label": "分镜", "config": {"scenes": 3}, "depends_on": ["t1"]},
    {"id": "t3", "node_id": "n3", "kind": "textToImage", "label": "图", "item_key": "scene-001", "index": 0, "config": {}, "depends_on": ["t2"]},
]


class TestEnqueue:
    def test_enqueue_creates_tasks(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        tasks = get_tasks_by_execution("exec-test")
        assert len(tasks) == 3

    def test_tasks_are_pending(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        t1 = get_task("t1")
        assert t1["status"] == "pending"


class TestClaim:
    def test_claim_ready_task(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        task = claim_task("worker-1")
        assert task is not None
        assert task["id"] == "t1"  # t1 没有依赖，应该首先被领取

    def test_claim_respects_dependencies(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        # 领取 t1
        claim_task("worker-1")
        # t2 依赖 t1，此时不应被领取
        task = claim_task("worker-1")
        assert task is None or task["id"] != "t2"

    def test_claim_after_completion(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        claim_task("worker-1")
        complete_task("t1")
        # 现在 t2 应该可领取
        task = claim_task("worker-1")
        assert task is not None
        assert task["id"] == "t2"

    def test_no_tasks_returns_none(self):
        task = claim_task("worker-1")
        assert task is None


class TestComplete:
    def test_complete_task(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        claim_task("worker-1")
        complete_task("t1")
        t1 = get_task("t1")
        assert t1["status"] == "completed"
        assert t1["completed_at"] is not None


class TestFail:
    def test_fail_propagates_to_downstream(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        claim_task("worker-1")
        complete_task("t1")
        claim_task("worker-1")
        skipped = fail_task("t2", "分镜生成失败")
        # t3 依赖 t2，应该被 skipped
        assert "t3" in skipped
        t3 = get_task("t3")
        assert t3["status"] == "skipped"


class TestCancel:
    def test_cancel_pending_task(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        cancel_task("t1")
        t1 = get_task("t1")
        assert t1["status"] == "cancelled"


class TestRecoverOrphans:
    def test_recover_moves_to_pending(self):
        enqueue_tasks("wf-test", "exec-test", SAMPLE_TASKS)
        task = claim_task("worker-1")
        assert task is not None
        # 手动设置 lease 已过期
        from backend.app.db.connection import get_connection
        conn = get_connection()
        conn.execute("UPDATE tasks SET lease_until = '2020-01-01T00:00:00' WHERE id = 't1'")
        conn.commit()
        orphans = recover_orphans("worker-2")
        assert "t1" in orphans
        t1 = get_task("t1")
        assert t1["status"] == "pending"
