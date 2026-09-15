"""WorkerPool 测试 — 多 Worker 并发、原子性、崩溃恢复。"""

import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest
from backend.app.db.connection import close_connection, init_db
from backend.app.engine.queue import claim_task, complete_task, enqueue_tasks, get_task
from backend.app.engine.worker import Worker, WorkerPool


# --- Fixtures ---


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
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


INDEPENDENT_TASKS = [
    {"id": f"t{i}", "node_id": f"n{i}", "kind": "textInput", "label": f"任务{i}", "config": {}, "depends_on": []}
    for i in range(1, 6)  # 5 independent tasks
]

CHAIN_TASKS = [
    {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "输入", "config": {}, "depends_on": []},
    {"id": "t2", "node_id": "n2", "kind": "textInput", "label": "中间", "config": {}, "depends_on": ["t1"]},
]


# --- Test Worker basic lifecycle ---


class TestWorker:
    def test_worker_starts_and_stops(self):
        """Worker 可以正常启动和停止。"""
        worker = Worker("test-worker", poll_interval=0.05)
        assert worker._running is False

        async def run():
            task = asyncio.create_task(worker.start())
            await asyncio.sleep(0.1)
            assert worker._running is True
            await worker.stop()
            await task
            assert worker._running is False

        asyncio.get_event_loop().run_until_complete(run())


# --- Test WorkerPool lifecycle ---


class TestWorkerPoolLifecycle:
    def test_pool_starts_correct_count(self):
        """WorkerPool 启动指定数量的 Worker。"""
        pool = WorkerPool(worker_count=3, poll_interval=0.05)

        async def run():
            await pool.start()
            assert len(pool.workers) == 3
            for i, w in enumerate(pool.workers):
                assert w.worker_id == f"worker-{i+1}"
            # Verify they are running
            await asyncio.sleep(0.1)
            assert pool.active_count == 3
            await pool.stop()
            await asyncio.sleep(0.1)
            assert pool.active_count == 0

        asyncio.get_event_loop().run_until_complete(run())

    def test_pool_stop_cancels_tasks(self):
        """WorkerPool stop 会取消所有 asyncio Task。"""
        pool = WorkerPool(worker_count=2, poll_interval=0.05)

        async def run():
            await pool.start()
            await asyncio.sleep(0.05)
            await pool.stop()
            for t in pool._tasks:
                assert t.cancelled() or t.done()

        asyncio.get_event_loop().run_until_complete(run())


# --- Test concurrent claim (no duplicate) ---


class TestConcurrentClaim:
    def test_multiple_workers_claim_different_tasks(self):
        """多个 Worker 同时 claim 不会重复领取同一任务。"""
        enqueue_tasks("wf-test", "exec-test", INDEPENDENT_TASKS)
        claimed = set()
        claim_count = 0

        # Simulate 3 workers claiming
        for _ in range(3):
            result = claim_task("worker-concurrent", lease_seconds=30)
            if result is not None:
                tid = result["id"]
                assert tid not in claimed, f"任务 {tid} 被重复领取！"
                claimed.add(tid)
                claim_count += 1

        # 3 tasks claimed from 5 independent tasks
        assert claim_count == 3
        assert len(claimed) == 3

    def test_claim_returns_none_when_exhausted(self):
        """所有可领取任务领完后返回 None。"""
        enqueue_tasks("wf-test", "exec-test", INDEPENDENT_TASKS)
        for _ in range(5):
            result = claim_task("worker-exhaust", lease_seconds=30)
            assert result is not None
        # Now all tasks are claimed
        result = claim_task("worker-exhaust", lease_seconds=30)
        assert result is None


# --- Test atomicity: simultaneous claim on same task ---


class TestClaimAtomicity:
    def test_simultaneous_claim_only_one_succeeds(self):
        """两个 Worker 同时 claim 同一任务，只有一个成功。"""
        enqueue_tasks("wf-test", "exec-test", [
            {"id": "single", "node_id": "n1", "kind": "textInput", "label": "唯一任务", "config": {}, "depends_on": []}
        ])

        results = []

        def try_claim(worker_id):
            result = claim_task(worker_id, lease_seconds=30)
            results.append(result is not None)

        # Sequential simulation (SQLite is single-process; true concurrency
        # requires threads, but BEGIN IMMEDIATE guarantees atomicity).
        # We verify the queue guarantees at the DB level.
        try_claim("worker-A")
        try_claim("worker-B")

        # First claim succeeds, second gets None (task already running)
        assert results[0] is True
        assert results[1] is False

    def test_concurrent_claim_with_threads(self):
        """多线程同时 claim，只有一个成功（BEGIN IMMEDIATE 保证）。"""
        enqueue_tasks("wf-test", "exec-test", [
            {"id": "thread-task", "node_id": "n1", "kind": "textInput", "label": "线程任务", "config": {}, "depends_on": []}
        ])

        import threading
        results = [None, None]

        def try_claim(idx):
            try:
                results[idx] = claim_task(f"thread-worker-{idx}", lease_seconds=30)
            except Exception:
                # BEGIN IMMEDIATE contention — expected under concurrent threads
                results[idx] = None

        threads = [threading.Thread(target=try_claim, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        claimed = [r for r in results if r is not None]
        assert len(claimed) == 1, f"Expected exactly 1 successful claim, got {len(claimed)}"


# --- Test worker crash resilience ---


class TestWorkerCrashResilience:
    def test_other_workers_continue_after_crash(self):
        """一个 Worker 崩溃后其他 Worker 继续工作。"""
        enqueue_tasks("wf-test", "exec-test", INDEPENDENT_TASKS)
        pool = WorkerPool(worker_count=2, poll_interval=0.05)

        async def run():
            await pool.start()
            await asyncio.sleep(0.1)

            # Simulate crash: stop one worker
            pool.workers[0]._running = False
            await asyncio.sleep(0.1)

            # Other worker should still be active
            assert pool.active_count == 1

            # Worker 1 crash didn't affect worker 2
            assert pool.workers[1]._running is True

            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())

    def test_orphan_recovery_across_workers(self):
        """超时任务可以被其他 Worker 回收。"""
        enqueue_tasks("wf-test", "exec-test", INDEPENDENT_TASKS)

        # Worker-1 claims task t1
        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None
        assert task["id"] == "t1"

        # Simulate lease expiry
        from backend.app.db.connection import get_connection
        conn = get_connection()
        conn.execute("UPDATE tasks SET lease_until = '2020-01-01T00:00:00' WHERE id = 't1'")
        conn.commit()

        # Worker-2 recovers orphans
        from backend.app.engine.queue import recover_orphans
        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert "t1" in orphans

        # Worker-2 can now claim the recovered task
        task2 = claim_task("worker-2", lease_seconds=30)
        assert task2 is not None
        assert task2["id"] == "t1"
        assert task2["worker_id"] == "worker-2"


# --- Test WorkerPool properties ---


class TestWorkerPoolProperties:
    def test_active_count_reflects_state(self):
        """active_count 反映实际运行状态。"""
        pool = WorkerPool(worker_count=2, poll_interval=0.05)

        async def run():
            assert pool.active_count == 0
            await pool.start()
            await asyncio.sleep(0.1)
            assert pool.active_count == 2
            pool.workers[0]._running = False
            assert pool.active_count == 1
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())
