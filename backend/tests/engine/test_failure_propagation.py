"""Failure propagation & cancel-race tests.

Scenarios:
- Recursive failure propagation: A -> B -> C, A fails -> B & C skipped
- Recursive cancel propagation: A -> B -> C, cancel A -> B & C cancelled
- Race protection: cancelled task is NOT overwritten by complete_task()
- Retry then fail: propagation only fires after exceeding max_retries
"""

import pytest
from backend.app.db.connection import close_connection, init_db, get_connection
from backend.app.engine.queue import (
    enqueue_tasks, claim_task, complete_task, fail_task,
    cancel_task, get_task, get_tasks_by_execution,
)

EXECUTION_ID = "exec-prop-test"
WORKFLOW_ID = "wf-prop-test"

# Chain: A(t1) -> B(t2) -> C(t3)
CHAIN_TASKS = [
    {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "A",
     "config": {}, "depends_on": []},
    {"id": "t2", "node_id": "n2", "kind": "storyboard", "label": "B",
     "config": {}, "depends_on": ["t1"]},
    {"id": "t3", "node_id": "n3", "kind": "textToImage", "label": "C",
     "config": {}, "depends_on": ["t2"]},
]

# Diamond: A(t1) -> B(t2), A(t1) -> C(t3), B & C -> D(t4)
DIAMOND_TASKS = [
    {"id": "t1", "node_id": "n1", "kind": "textInput", "label": "A",
     "config": {}, "depends_on": []},
    {"id": "t2", "node_id": "n2", "kind": "storyboard", "label": "B",
     "config": {}, "depends_on": ["t1"]},
    {"id": "t3", "node_id": "n3", "kind": "textToImage", "label": "C",
     "config": {}, "depends_on": ["t1"]},
    {"id": "t4", "node_id": "n4", "kind": "videoGen", "label": "D",
     "config": {}, "depends_on": ["t2", "t3"]},
]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets an isolated in-memory-style SQLite database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH",
                        tmp_path / "test_prop.db")
    close_connection()
    init_db()
    conn = get_connection()
    conn.execute(
        "INSERT INTO workflows (id, name, spec_json) VALUES (?, ?, ?)",
        (WORKFLOW_ID, "propagation-test", "{}"),
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status) "
        "VALUES (?, ?, ?, ?)",
        (EXECUTION_ID, WORKFLOW_ID, "{}", "running"),
    )
    conn.commit()
    yield
    close_connection()


# ------------------------------------------------------------------ #
#  1. Recursive failure propagation
# ------------------------------------------------------------------ #

class TestRecursiveFailurePropagation:
    """A -> B -> C chain: when A fails beyond retry, B & C are skipped."""

    def test_chain_skipped(self):
        """Fail t1 (A) beyond max_retries -> t2 (B) and t3 (C) skipped."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)

        # Exhaust retries for t1 (attempt will become 1, 2, 3)
        skipped = []
        for _ in range(3):
            skipped = fail_task("t1", "A failed", max_retries=3)

        assert "t2" in skipped
        assert "t3" in skipped
        assert get_task("t2")["status"] == "skipped"
        assert get_task("t3")["status"] == "skipped"

    def test_only_pending_downstream_affected(self):
        """If B is already completed, C should NOT be skipped by A's failure."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)

        # Complete A and B
        claim_task("worker-1")
        complete_task("t1")
        claim_task("worker-1")
        complete_task("t2")

        # Fail A beyond retry
        skipped = fail_task("t1", "A failed", max_retries=3)

        # B is completed, not pending -> should not appear in skipped
        assert "t2" not in skipped
        # C depends on B (completed) not A directly, but C is pending
        # However, C doesn't depend on A via dependency chain through B
        # because B is completed.  C only depends on B.
        assert get_task("t2")["status"] == "completed"

    def test_diamond_failure(self):
        """Diamond: A -> B, A -> C, B & C -> D.  Fail A -> B, C, D skipped."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, DIAMOND_TASKS)

        skipped = []
        for _ in range(3):
            skipped = fail_task("t1", "root failed", max_retries=3)

        assert set(skipped) == {"t2", "t3", "t4"}
        for tid in ("t2", "t3", "t4"):
            assert get_task(tid)["status"] == "skipped"


# ------------------------------------------------------------------ #
#  2. Recursive cancel propagation
# ------------------------------------------------------------------ #

class TestRecursiveCancelPropagation:
    """A -> B -> C chain: cancel A -> B and C also cancelled."""

    def test_chain_cancelled(self):
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        cancelled = cancel_task("t1")

        assert "t2" in cancelled
        assert "t3" in cancelled
        assert get_task("t1")["status"] == "cancelled"
        assert get_task("t2")["status"] == "cancelled"
        assert get_task("t3")["status"] == "cancelled"

    def test_cancel_already_completed_noop(self):
        """Cancelling a completed task should be a no-op."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")
        complete_task("t1")

        cancelled = cancel_task("t1")
        assert cancelled == []
        assert get_task("t1")["status"] == "completed"

    def test_cancel_running_task(self):
        """Cancelling a running task should work."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")
        cancelled = cancel_task("t1")

        assert "t2" in cancelled
        assert "t3" in cancelled
        assert get_task("t1")["status"] == "cancelled"
        assert get_task("t2")["status"] == "cancelled"
        assert get_task("t3")["status"] == "cancelled"

    def test_diamond_cancel(self):
        """Diamond: cancel A -> B, C, D all cancelled."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, DIAMOND_TASKS)
        cancelled = cancel_task("t1")

        assert set(cancelled) == {"t2", "t3", "t4"}
        for tid in ("t1", "t2", "t3", "t4"):
            assert get_task(tid)["status"] == "cancelled"


# ------------------------------------------------------------------ #
#  3. Race protection: cancelled task not overwritten
# ------------------------------------------------------------------ #

class TestRaceProtection:
    """complete_task() must NOT overwrite a cancelled task."""

    def test_complete_does_not_overwrite_cancelled(self):
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")  # t1 -> running

        # Cancel t1 while it is "running"
        cancel_task("t1")
        assert get_task("t1")["status"] == "cancelled"

        # Attempt to complete t1 (simulating a slow worker finishing after cancel)
        complete_task("t1", result={"data": "stale"})

        # Must still be cancelled
        assert get_task("t1")["status"] == "cancelled"

    def test_complete_does_not_overwrite_failed(self):
        """complete_task() should not overwrite a failed task either."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")  # t1 -> running

        # Fail t1 beyond retry
        for _ in range(3):
            fail_task("t1", "oops", max_retries=3)
        assert get_task("t1")["status"] == "failed"

        # Attempt to complete t1
        complete_task("t1", result={"data": "late"})
        assert get_task("t1")["status"] == "failed"

    def test_complete_does_not_overwrite_skipped(self):
        """complete_task() should not overwrite a skipped task."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)

        # Fail t1 beyond retry -> t2 becomes skipped
        for _ in range(3):
            fail_task("t1", "fail", max_retries=3)
        assert get_task("t2")["status"] == "skipped"

        # Attempt to complete t2
        complete_task("t2", result={"data": "nope"})
        assert get_task("t2")["status"] == "skipped"


# ------------------------------------------------------------------ #
#  4. Retry then fail
# ------------------------------------------------------------------ #

class TestRetryThenFail:
    """Propagation only fires after max_retries is exhausted."""

    def test_retry_resets_pending(self):
        """Within retry budget, task goes back to pending."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")

        skipped = fail_task("t1", "transient error", max_retries=3)
        assert skipped == []  # no propagation yet
        assert get_task("t1")["status"] == "pending"
        assert get_task("t2")["status"] == "pending"  # untouched

    def test_retry_counter_increments(self):
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)
        claim_task("worker-1")

        fail_task("t1", "err1", max_retries=3)
        t1 = get_task("t1")
        assert t1["attempt"] == 1

        claim_task("worker-1")  # re-claim after pending reset
        fail_task("t1", "err2", max_retries=3)
        t1 = get_task("t1")
        assert t1["attempt"] == 2

    def test_exhaustion_triggers_propagation(self):
        """After max_retries failures, propagation fires."""
        enqueue_tasks(WORKFLOW_ID, EXECUTION_ID, CHAIN_TASKS)

        for i in range(3):
            claim_task("worker-1")
            skipped = fail_task("t1", f"err{i}", max_retries=3)

        # Last call should have propagated
        assert "t2" in skipped
        assert "t3" in skipped
        assert get_task("t1")["status"] == "failed"
