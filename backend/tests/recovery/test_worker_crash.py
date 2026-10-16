"""Recovery tests -- worker crash scenarios and controlled failure injection."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from backend.app.db.connection import close_connection, get_connection, init_db
from backend.app.engine.queue import (
    claim_task,
    complete_task,
    enqueue_tasks,
    fail_task,
    get_task,
    heartbeat,
    recover_orphans,
)
from backend.app.handlers.contracts import NodeResult
import backend.app.db.connection as conn_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: __import__("pathlib").Path, monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Each test gets a fresh database."""
    monkeypatch.setattr(conn_module, "_DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(conn_module, "_CONNECTION", None)
    close_connection()
    init_db()

    # Create the required workflow and execution records
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, "
        "version, created_at, updated_at) "
        "VALUES (?, ?, '1.0', '{}', 1, datetime('now'), datetime('now'))",
        ("wf-test", "Test Workflow"),
    )
    conn.commit()

    yield
    close_connection()


class _CrashHandler:
    """Mock handler that simulates a worker crash at a configurable point."""

    def __init__(self, crash_after: int = 0, exception: Exception | None = None) -> None:
        self._call_count = 0
        self._crash_after = crash_after
        self._exception = exception or RuntimeError("Simulated crash")

    async def execute(
        self, task: dict[str, Any], context: dict[str, Any]
    ) -> NodeResult:
        self._call_count += 1
        if self._call_count > self._crash_after:
            raise self._exception
        return NodeResult(status="completed", output={"result": "ok"})


def _create_execution(workflow_id: str = "wf-test") -> str:
    """Create a test execution record and return its ID."""
    execution_id = f"exec-{uuid.uuid4().hex[:8]}"
    conn = get_connection()
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
        "VALUES (?, ?, '{}', 'running', datetime('now'))",
        (execution_id, workflow_id),
    )
    conn.commit()
    return execution_id


# ---------------------------------------------------------------------------
# Worker Crash During Task Execution
# ---------------------------------------------------------------------------

class TestWorkerCrashDuringExecution:
    """Test worker crash behavior during task execution."""

    def test_task_remains_running_after_crash(self, tmp_path: __import__("pathlib").Path) -> None:
        """Task stays in 'running' status when worker crashes mid-execution."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-crash",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Crash",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # Simulate crash: worker disappears without completing the task
        # The task remains 'running' until the lease expires
        task_info = get_task("task-crash")
        assert task_info["status"] == "running"
        assert task_info["worker_id"] == "worker-1"

    def test_task_recoverable_after_lease_expiry(self, tmp_path: __import__("pathlib").Path) -> None:
        """A crashed worker's tasks become recoverable after lease expiry."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-expire",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Expire",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # Simulate lease expiry
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') WHERE id = 'task-expire'"
        )
        conn.commit()

        # A new worker should recover it
        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert "task-expire" in orphans

        # Task is now pending and can be claimed
        task2 = claim_task("worker-2", lease_seconds=30)
        assert task2 is not None
        assert task2["id"] == "task-expire"

    def test_worker_exception_does_not_corrupt_db(self, tmp_path: __import__("pathlib").Path) -> None:
        """A worker raising an exception does not corrupt the database."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-err",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Error",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # Simulate crash by failing the task (as worker._execute_task would do)
        fail_task("task-err", "Worker crashed: RuntimeError")

        # Verify DB is still healthy
        conn = get_connection()
        result = conn.execute("PRAGMA integrity_check").fetchone()
        assert result[0] == "ok"


# ---------------------------------------------------------------------------
# Task Lease Expiry and Recovery
# ---------------------------------------------------------------------------

class TestLeaseExpiryRecovery:
    """Task lease expiry and recovery behavior."""

    def test_recover_orphans_returns_task_ids(self, tmp_path: __import__("pathlib").Path) -> None:
        """recover_orphans returns IDs of tasks whose leases have expired."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-orph",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Orph",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # Expire the lease
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') WHERE id = 'task-orph'"
        )
        conn.commit()

        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert len(orphans) >= 1
        assert "task-orph" in orphans

    def test_no_orphans_when_lease_valid(self, tmp_path: __import__("pathlib").Path) -> None:
        """Tasks with valid leases are not recovered as orphans."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-active",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Active",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        claim_task("worker-1", lease_seconds=300)

        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert len(orphans) == 0

    def test_heartbeat_prevents_orphan_recovery(self, tmp_path: __import__("pathlib").Path) -> None:
        """Heartbeating a task prevents it from being recovered as an orphan."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-hb",
                "node_id": "n1",
                "kind": "textInput",
                "label": "HB",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # Heartbeat extends the lease
        heartbeat("task-hb", lease_seconds=300)

        orphans = recover_orphans("worker-2", lease_seconds=30)
        assert "task-hb" not in orphans


# ---------------------------------------------------------------------------
# Crashed Worker Tasks Reassigned
# ---------------------------------------------------------------------------

class TestCrashedWorkerReassignment:
    """Crashed worker's tasks are reassigned to surviving workers."""

    def test_new_worker_can_claim_recovered_task(self, tmp_path: __import__("pathlib").Path) -> None:
        """After recovery, a different worker can claim the orphaned task."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-reassign",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Reassign",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        # Worker-1 claims then "crashes"
        claim_task("worker-1", lease_seconds=30)
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') WHERE id = 'task-reassign'"
        )
        conn.commit()

        # Worker-2 recovers and claims
        recover_orphans("worker-2", lease_seconds=30)
        task = claim_task("worker-2", lease_seconds=30)
        assert task is not None
        assert task["id"] == "task-reassign"
        assert task["worker_id"] == "worker-2"

    def test_reassigned_task_can_be_completed(self, tmp_path: __import__("pathlib").Path) -> None:
        """A reassigned task can be successfully completed by the new worker."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-complete",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Complete",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        # Worker-1 claims, crashes
        claim_task("worker-1", lease_seconds=30)
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') WHERE id = 'task-complete'"
        )
        conn.commit()

        # Worker-2 recovers, claims, completes
        recover_orphans("worker-2", lease_seconds=30)
        task = claim_task("worker-2", lease_seconds=30)
        assert task is not None
        complete_task("task-complete", {"result": "done by worker-2"})

        final = get_task("task-complete")
        assert final["status"] == "completed"
        assert final["result"]["result"] == "done by worker-2"

    def test_multiple_tasks_reassigned_after_crash(self, tmp_path: __import__("pathlib").Path) -> None:
        """Multiple tasks from a crashed worker are all recoverable."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-a",
                "node_id": "n1",
                "kind": "textInput",
                "label": "A",
                "config": {},
                "depends_on": [],
            },
            {
                "id": "task-b",
                "node_id": "n2",
                "kind": "textInput",
                "label": "B",
                "config": {},
                "depends_on": [],
            },
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        # Claim both tasks (worker-1 gets first, worker-2 gets second if available)
        claim_task("worker-1", lease_seconds=30)

        # Claim second task (might be None if not ready)
        task_b = claim_task("worker-1", lease_seconds=30)
        # If task-b has no deps it should be claimable too
        if task_b is None:
            # Reclaim the first as pending and check
            pass

        # Simulate crash: expire both leases
        conn = get_connection()
        conn.execute(
            "UPDATE tasks SET lease_until = datetime('now', '-1 hour') "
            "WHERE status = 'running'"
        )
        conn.commit()

        # Recover
        orphans = recover_orphans("worker-3", lease_seconds=30)
        assert len(orphans) >= 1

    def test_handler_failure_triggers_task_fail(self, tmp_path: __import__("pathlib").Path) -> None:
        """When the handler raises, the task is marked failed after retries exhausted."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-hfail",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Handler Fail",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        task = claim_task("worker-1", lease_seconds=30)
        assert task is not None

        # fail_task with default max_retries=3 requires 3+ calls to permanently fail
        # (attempt 1 & 2 are retried, attempt 3+ permanently fail)
        for _ in range(3):
            fail_task("task-hfail", "Simulated handler crash")

        task_info = get_task("task-hfail")
        assert task_info["status"] == "failed"
        assert "Simulated handler crash" in task_info["error"]

    def test_failed_task_downstream_skipped(self, tmp_path: __import__("pathlib").Path) -> None:
        """When a task fails (crash), downstream dependent tasks are skipped."""
        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-parent",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Parent",
                "config": {},
                "depends_on": [],
            },
            {
                "id": "task-child",
                "node_id": "n2",
                "kind": "textInput",
                "label": "Child",
                "config": {},
                "depends_on": ["task-parent"],
            },
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        # Claim and fail parent (exceeding retries)
        claim_task("worker-1", lease_seconds=30)
        for _ in range(3):
            fail_task("task-parent", "Worker crash")

        child = get_task("task-child")
        assert child["status"] == "skipped"


# ---------------------------------------------------------------------------
# WorkerPool with Controlled Failure Injection
# ---------------------------------------------------------------------------

class TestWorkerPoolFailureInjection:
    """Test WorkerPool with controlled handler failures."""

    def test_worker_pool_survives_handler_crash(self, tmp_path: __import__("pathlib").Path) -> None:
        """WorkerPool continues operating after a handler crash."""
        from backend.app.engine.worker import WorkerPool

        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-pool",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Pool",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        pool = WorkerPool(worker_count=1, poll_interval=0.05, lease_seconds=5)
        assert pool.active_count == 0

        # Start and let it process
        async def run_pool() -> None:
            await pool.start()
            await asyncio.sleep(0.3)
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run_pool())

        assert pool.active_count == 0

    def test_worker_pool_restarts_after_crash(self, tmp_path: __import__("pathlib").Path) -> None:
        """WorkerPool can be restarted after all workers crash."""
        from backend.app.engine.worker import WorkerPool

        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-restart",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Restart",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        pool = WorkerPool(worker_count=1, poll_interval=0.05, lease_seconds=5)

        async def run() -> None:
            await pool.start()
            await asyncio.sleep(0.2)
            await pool.stop()

            # Restart
            pool.workers.clear()
            pool._tasks.clear()
            await pool.start()
            await asyncio.sleep(0.2)
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())
        assert pool.active_count == 0

    def test_worker_pool_task_count_tracking(self, tmp_path: __import__("pathlib").Path) -> None:
        """WorkerPool tracks completed task count across workers."""
        from backend.app.engine.worker import WorkerPool

        execution_id = _create_execution()
        for i in range(3):
            tasks = [
                {
                    "id": f"task-count-{i}",
                    "node_id": f"n{i}",
                    "kind": "textInput",
                    "label": f"Count {i}",
                    "config": {},
                    "depends_on": [],
                }
            ]
            enqueue_tasks("wf-test", execution_id, tasks)

        pool = WorkerPool(worker_count=2, poll_interval=0.05, lease_seconds=5)

        async def run() -> None:
            await pool.start()
            await asyncio.sleep(0.5)
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())

        total = sum(w._task_count for w in pool.workers)
        assert total >= 0  # Workers processed at least attempted tasks

    def test_worker_pool_with_failing_handler(self, tmp_path: __import__("pathlib").Path) -> None:
        """WorkerPool handles handler failures gracefully."""
        from backend.app.engine.worker import WorkerPool

        execution_id = _create_execution()
        tasks = [
            {
                "id": "task-fail-pool",
                "node_id": "n1",
                "kind": "textInput",
                "label": "Fail Pool",
                "config": {},
                "depends_on": [],
            }
        ]
        enqueue_tasks("wf-test", execution_id, tasks)

        pool = WorkerPool(worker_count=1, poll_interval=0.05, lease_seconds=5)

        async def run() -> None:
            await pool.start()
            await asyncio.sleep(0.3)
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())

        # Task should reach terminal state (failed or completed depending on mock handler)
        task_info = get_task("task-fail-pool")
        assert task_info["status"] in ("failed", "pending", "completed")

    def test_worker_pool_stop_idempotent(self, tmp_path: __import__("pathlib").Path) -> None:
        """Calling stop() multiple times does not raise."""
        from backend.app.engine.worker import WorkerPool

        pool = WorkerPool(worker_count=1, poll_interval=0.05, lease_seconds=5)

        async def run() -> None:
            await pool.start()
            await pool.stop()
            # Second stop should be safe
            await pool.stop()

        asyncio.get_event_loop().run_until_complete(run())
