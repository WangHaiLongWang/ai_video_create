"""Performance benchmarks for the ai_video_create backend.

Covers:
1. Workflow compilation (DAG validation, topological sort)
2. Scheduler throughput (schedule_next_tasks, task completions)
3. API latency (FastAPI TestClient, non-AI endpoints)
4. WorkerPool concurrency
5. Memory usage during 100-node workflow compilation

All benchmarks use mock providers -- no real API calls are made.

Run with:
    cd backend && python -m pytest tests/performance/test_benchmarks.py -v --tb=short -m performance
"""

from __future__ import annotations

import asyncio
import uuid
import time

import pytest

from backend.app.engine.compiler import compile_workflow, topological_sort
from backend.tests.performance.benchmark_reporter import get_collector
from backend.tests.performance.conftest import (
    BenchmarkTimer,
    MemoryTracker,
    generate_diamond_workflow,
    generate_linear_workflow,
    generate_mixed_dag,
)

# Mark every test in this module as a performance benchmark
pytestmark = pytest.mark.performance


# ======================================================================
# 1. Workflow Compilation Benchmark
# ======================================================================


class TestCompilationBenchmark:
    """Benchmark DAG compilation: topological sort + ExecutionPlan generation."""

    @staticmethod
    def _compile_and_count(spec: dict) -> int:
        plan = compile_workflow(spec)
        return len(plan.tasks)

    def test_compile_linear_10(self, benchmark_timer: BenchmarkTimer) -> None:
        """10-node linear workflow compilation."""
        spec = generate_linear_workflow(10)
        benchmark_timer.run(self._compile_and_count, spec)
        s = benchmark_timer.summary()

        assert benchmark_timer.min < 0.100, f"10-node min {benchmark_timer.min:.4f}s >= 100ms"
        get_collector().record(
            "compile.linear_10", s, category="compiler",
            assertions=["10-node compiles in < 100ms"],
            passed=benchmark_timer.min < 0.100,
        )

    def test_compile_linear_50(self, benchmark_timer: BenchmarkTimer) -> None:
        """50-node linear workflow compilation."""
        spec = generate_linear_workflow(50)
        benchmark_timer.run(self._compile_and_count, spec)
        s = benchmark_timer.summary()

        assert benchmark_timer.min < 0.100, f"50-node min {benchmark_timer.min:.4f}s >= 100ms"
        get_collector().record(
            "compile.linear_50", s, category="compiler",
            assertions=["50-node compiles in < 100ms"],
            passed=benchmark_timer.min < 0.100,
        )

    def test_compile_linear_100(self, benchmark_timer: BenchmarkTimer) -> None:
        """100-node linear workflow -- must compile in < 100 ms (P95)."""
        spec = generate_linear_workflow(100)
        benchmark_timer.run(self._compile_and_count, spec)
        s = benchmark_timer.summary()

        p95 = benchmark_timer.p95
        assert p95 < 0.100, f"100-node P95 {p95:.4f}s >= 100ms"
        get_collector().record(
            "compile.linear_100", s, category="compiler",
            assertions=["100-node P95 < 100ms"],
            passed=p95 < 0.100,
        )

    def test_compile_diamond_50(self, benchmark_timer: BenchmarkTimer) -> None:
        """Diamond (fan-out/fan-in) with 50 parallel branches."""
        spec = generate_diamond_workflow(50)
        benchmark_timer.run(self._compile_and_count, spec)
        s = benchmark_timer.summary()

        assert benchmark_timer.min < 0.100
        get_collector().record(
            "compile.diamond_50", s, category="compiler",
            assertions=["Diamond-50 compiles in < 100ms"],
            passed=benchmark_timer.min < 0.100,
        )

    def test_compile_mixed_dag_100(self, benchmark_timer: BenchmarkTimer) -> None:
        """Mixed DAG with 100 nodes -- realistic workload."""
        spec = generate_mixed_dag(100)
        benchmark_timer.run(self._compile_and_count, spec)
        s = benchmark_timer.summary()

        p95 = benchmark_timer.p95
        assert p95 < 0.100, f"Mixed-100 P95 {p95:.4f}s >= 100ms"
        get_collector().record(
            "compile.mixed_100", s, category="compiler",
            assertions=["Mixed-DAG 100-node P95 < 100ms"],
            passed=p95 < 0.100,
        )

    def test_topo_sort_1000(self, benchmark_timer: BenchmarkTimer) -> None:
        """Topological sort on a 1000-node linear chain."""
        nodes = [{"id": f"n{i}", "data": {}} for i in range(1000)]
        edges = [
            {"id": f"e{i}", "source": f"n{i}", "target": f"n{i + 1}"}
            for i in range(999)
        ]

        def _run() -> int:
            result = topological_sort(nodes, edges)
            return len(result)

        benchmark_timer.run(_run)
        s = benchmark_timer.summary()

        assert benchmark_timer.p95 < 0.100
        get_collector().record(
            "compile.topo_sort_1000", s, category="compiler",
            assertions=["Topo-sort 1000 nodes P95 < 100ms"],
            passed=benchmark_timer.p95 < 0.100,
        )


# ======================================================================
# 2. Scheduler Throughput Benchmark
# ======================================================================


class TestSchedulerThroughputBenchmark:
    """Benchmark scheduler's scheduling and task completion processing."""

    @pytest.fixture(autouse=True)
    def _init_mock_handlers(self) -> None:
        """Ensure mock handlers are registered for any handler lookups."""
        from backend.app.handlers import init_mock_handlers
        init_mock_handlers()

    @staticmethod
    def _populate_tasks(bench_exec: str, count: int) -> None:
        """Insert *count* independent tasks into the queue."""
        from backend.app.engine.queue import enqueue_tasks

        tasks = [
            {
                "id": f"task-{i}",
                "node_id": f"n{i}",
                "kind": "textInput",
                "label": f"Task {i}",
                "config": {},
                "depends_on": [],
            }
            for i in range(count)
        ]
        enqueue_tasks("wf-bench", bench_exec, tasks)

    def test_schedule_10_tasks(self, bench_exec: str, benchmark_timer: BenchmarkTimer) -> None:
        """Schedule 10 independent tasks."""
        self._populate_tasks(bench_exec, 10)

        from backend.app.db.connection import get_connection

        async def _timed():
            from backend.app.engine.scheduler import Scheduler
            sched = Scheduler()
            start = time.perf_counter()
            ready = await sched.schedule_next_tasks(bench_exec)
            return time.perf_counter() - start, ready

        loop = asyncio.new_event_loop()
        try:
            durations = []
            for _ in range(benchmark_timer.iterations):
                conn = get_connection()
                conn.execute("UPDATE tasks SET status = 'pending', worker_id = NULL")
                conn.commit()
                elapsed, _ = loop.run_until_complete(_timed())
                durations.append(elapsed)
            benchmark_timer.samples = durations
        finally:
            loop.close()

        s = benchmark_timer.summary()
        get_collector().record(
            "scheduler.schedule_10", s, category="scheduler",
            assertions=["10 tasks scheduled in < 100ms"],
            passed=benchmark_timer.p95 < 0.100,
        )
        assert benchmark_timer.p95 < 0.100

    def test_schedule_50_tasks(self, bench_exec: str, benchmark_timer: BenchmarkTimer) -> None:
        """Schedule 50 independent tasks."""
        self._populate_tasks(bench_exec, 50)

        from backend.app.db.connection import get_connection

        async def _timed():
            from backend.app.engine.scheduler import Scheduler
            sched = Scheduler()
            start = time.perf_counter()
            ready = await sched.schedule_next_tasks(bench_exec)
            return time.perf_counter() - start, ready

        loop = asyncio.new_event_loop()
        try:
            durations = []
            for _ in range(benchmark_timer.iterations):
                conn = get_connection()
                conn.execute("UPDATE tasks SET status = 'pending', worker_id = NULL")
                conn.commit()
                elapsed, _ = loop.run_until_complete(_timed())
                durations.append(elapsed)
            benchmark_timer.samples = durations
        finally:
            loop.close()

        s = benchmark_timer.summary()
        get_collector().record(
            "scheduler.schedule_50", s, category="scheduler",
            assertions=["50 tasks scheduled in < 100ms"],
            passed=benchmark_timer.p95 < 0.100,
        )

    def test_schedule_100_tasks(self, bench_exec: str, benchmark_timer: BenchmarkTimer) -> None:
        """Schedule 100 independent tasks -- must complete in < 200 ms."""
        self._populate_tasks(bench_exec, 100)

        from backend.app.db.connection import get_connection

        async def _timed():
            from backend.app.engine.scheduler import Scheduler
            sched = Scheduler()
            start = time.perf_counter()
            ready = await sched.schedule_next_tasks(bench_exec)
            return time.perf_counter() - start, ready

        loop = asyncio.new_event_loop()
        try:
            durations = []
            for _ in range(benchmark_timer.iterations):
                conn = get_connection()
                conn.execute("UPDATE tasks SET status = 'pending', worker_id = NULL")
                conn.commit()
                elapsed, _ = loop.run_until_complete(_timed())
                durations.append(elapsed)
            benchmark_timer.samples = durations
        finally:
            loop.close()

        s = benchmark_timer.summary()
        p95 = benchmark_timer.p95
        get_collector().record(
            "scheduler.schedule_100", s, category="scheduler",
            assertions=["100 tasks scheduled in < 200ms"],
            passed=p95 < 0.200,
        )
        assert p95 < 0.200, f"100 tasks P95 {p95:.4f}s >= 200ms"

    def test_task_completion_throughput(self, bench_exec: str, benchmark_timer: BenchmarkTimer) -> None:
        """Measure time to claim and complete 100 tasks."""
        from backend.app.engine.queue import enqueue_tasks, claim_task, complete_task
        from backend.app.db.connection import get_connection

        self._populate_tasks(bench_exec, 100)

        durations = []
        for _ in range(benchmark_timer.iterations):
            conn = get_connection()
            conn.execute(
                "UPDATE tasks SET status = 'pending', worker_id = NULL, "
                "lease_until = NULL, started_at = NULL, completed_at = NULL"
            )
            conn.commit()

            start = time.perf_counter()
            for _ in range(100):
                task = claim_task("bench-worker", lease_seconds=30)
                if task:
                    complete_task(task["id"])
            elapsed = time.perf_counter() - start
            durations.append(elapsed)
        benchmark_timer.samples = durations

        s = benchmark_timer.summary()
        get_collector().record(
            "scheduler.completion_100", s, category="scheduler",
            assertions=["100 claim+complete cycles < 2s"],
            passed=benchmark_timer.p95 < 2.0,
        )
        assert benchmark_timer.p95 < 2.0


# ======================================================================
# 3. API Latency Benchmark
# ======================================================================


def _api_bench_lifespan(app):
    """Minimal lifespan that only initializes the DB (no worker pool)."""
    from contextlib import asynccontextmanager
    from backend.app.db.connection import init_db

    @asynccontextmanager
    async def _inner(app):
        init_db()
        yield

    return _inner(app)


class TestAPILatencyBenchmark:
    """Benchmark common REST API endpoints using FastAPI TestClient.

    Only non-AI endpoints are tested (workflow CRUD, execution status).
    """

    @pytest.fixture(autouse=True)
    def _setup_bench_db(self, bench_db: str) -> None:
        """Ensure the global DB points to our bench DB before any test runs."""
        import backend.app.db.connection as conn_module
        conn_module._DB_PATH = bench_db
        conn_module._CONNECTION = None
        from backend.app.db.connection import close_connection, init_db
        close_connection()
        init_db()

    @pytest.fixture()
    def client(self, _setup_bench_db):
        """Create a FastAPI TestClient with mock handlers and isolated DB."""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        from backend.app.handlers import init_mock_handlers
        from backend.app.middleware import SecurityMiddleware

        init_mock_handlers()

        # Override lifespan to skip worker pool startup for benchmarking
        original_lifespan = app.router.lifespan_context
        app.router.lifespan_context = _api_bench_lifespan

        # Build the middleware stack to get access to instances,
        # then bump the rate limit so benchmarks aren't throttled.
        # Force-build the middleware stack if not yet built.
        _ = app.middleware_stack  # noqa: B018

        # Walk the ASGI middleware chain to find SecurityMiddleware
        current = getattr(app, '_middleware_stack', None) or app.middleware_stack
        while current is not None:
            if isinstance(current, SecurityMiddleware):
                current.rate_limit = 100_000  # effectively no limit during benchmarks
                current._request_counts.clear()
                break
            current = getattr(current, 'app', None)

        with TestClient(app) as c:
            yield c

        app.router.lifespan_context = original_lifespan

    @staticmethod
    def _compute_stats(durations: list[float]) -> dict:
        """Compute percentile stats from a list of durations."""
        sorted_d = sorted(durations)
        n = len(sorted_d)
        return {
            "iterations": n,
            "min_s": round(min(sorted_d), 6),
            "max_s": round(max(sorted_d), 6),
            "avg_s": round(sum(sorted_d) / n, 6),
            "p50_s": round(sorted_d[n // 2], 6),
            "p95_s": round(sorted_d[int(n * 0.95)], 6),
            "p99_s": round(sorted_d[int(n * 0.99)], 6),
        }

    def test_get_workflows(self, client) -> None:
        """GET /api/workflows -- list workflows."""
        durations = []
        for _ in range(50):
            start = time.perf_counter()
            resp = client.get("/api/workflows")
            durations.append(time.perf_counter() - start)
            assert resp.status_code == 200

        s = self._compute_stats(durations)
        get_collector().record(
            "api.get_workflows", s, category="api",
            assertions=["GET /api/workflows P95 < 100ms"],
            passed=s["p95_s"] < 0.100,
        )
        assert s["p95_s"] < 0.100, f"GET /api/workflows P95 {s['p95_s']:.4f}s"

    def test_post_workflow(self, client) -> None:
        """POST /api/workflows -- create a workflow (unique ID per request)."""
        durations = []
        for _ in range(50):
            spec = {
                "id": f"bench-wf-{uuid.uuid4().hex[:8]}",
                "name": "API Benchmark",
                "nodes": [
                    {
                        "id": "n0", "type": "studio",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "label": "Input", "description": "",
                            "kind": "textInput", "outputType": "text", "config": {},
                        },
                    },
                ],
                "edges": [],
            }
            start = time.perf_counter()
            resp = client.post("/api/workflows", json=spec)
            durations.append(time.perf_counter() - start)
            assert resp.status_code == 201

        s = self._compute_stats(durations)
        get_collector().record(
            "api.post_workflow", s, category="api",
            assertions=["POST /api/workflows P95 < 100ms"],
            passed=s["p95_s"] < 0.100,
        )
        assert s["p95_s"] < 0.100

    def test_get_workflow_by_id(self, client) -> None:
        """GET /api/workflows/{id} -- retrieve a single workflow."""
        spec = {
            "id": "bench-wf-get",
            "name": "Get Benchmark",
            "nodes": [],
            "edges": [],
        }
        client.post("/api/workflows", json=spec)

        durations = []
        for _ in range(50):
            start = time.perf_counter()
            resp = client.get("/api/workflows/bench-wf-get")
            durations.append(time.perf_counter() - start)
            assert resp.status_code == 200

        s = self._compute_stats(durations)
        get_collector().record(
            "api.get_workflow_by_id", s, category="api",
            assertions=["GET /api/workflows/{id} P95 < 100ms"],
            passed=s["p95_s"] < 0.100,
        )
        assert s["p95_s"] < 0.100

    def test_start_execution(self, client) -> None:
        """POST /api/executions/{wf_id}/start -- start an execution."""
        # Pre-create workflows for each iteration.
        # Each workflow must have unique node IDs to avoid task ID collisions.
        iterations = 20
        wf_ids = []
        for i in range(iterations):
            wf_id = f"bench-exec-{uuid.uuid4().hex[:8]}"
            node_id = f"node-{uuid.uuid4().hex[:8]}"
            wf_ids.append(wf_id)
            spec = {
                "id": wf_id,
                "name": f"Exec Benchmark {i}",
                "nodes": [
                    {
                        "id": node_id, "type": "studio",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "label": "Input", "description": "",
                            "kind": "textInput", "outputType": "text", "config": {},
                        },
                    },
                ],
                "edges": [],
            }
            client.post("/api/workflows", json=spec)

        durations = []
        for i in range(iterations):
            start = time.perf_counter()
            resp = client.post(f"/api/executions/{wf_ids[i]}/start")
            durations.append(time.perf_counter() - start)
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

        s = self._compute_stats(durations)
        get_collector().record(
            "api.start_execution", s, category="api",
            assertions=["POST /start P95 < 100ms"],
            passed=s["p95_s"] < 0.100,
        )
        assert s["p95_s"] < 0.100

    def test_get_execution(self, client) -> None:
        """GET /api/executions/{id} -- get execution status."""
        unique_id = uuid.uuid4().hex[:8]
        node_id = f"node-{unique_id}"
        spec = {
            "id": f"bench-wf-status-{unique_id}",
            "name": "Status Benchmark",
            "nodes": [
                {
                    "id": node_id, "type": "studio",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "label": "Input", "description": "",
                        "kind": "textInput", "outputType": "text", "config": {},
                    },
                },
            ],
            "edges": [],
        }
        client.post("/api/workflows", json=spec)
        resp = client.post(f"/api/executions/bench-wf-status-{unique_id}/start")
        exec_id = resp.json()["id"]

        durations = []
        for _ in range(50):
            start = time.perf_counter()
            resp = client.get(f"/api/executions/{exec_id}")
            durations.append(time.perf_counter() - start)
            assert resp.status_code == 200

        s = self._compute_stats(durations)
        get_collector().record(
            "api.get_execution", s, category="api",
            assertions=["GET /executions/{id} P95 < 100ms"],
            passed=s["p95_s"] < 0.100,
        )
        assert s["p95_s"] < 0.100


# ======================================================================
# 4. WorkerPool Concurrency Benchmark
# ======================================================================


class TestWorkerPoolConcurrencyBenchmark:
    """Benchmark WorkerPool with different concurrency levels.

    Uses mock handlers that simulate processing delay.
    Verifies that 4 workers outperform 2 workers.
    """

    @pytest.fixture(autouse=True)
    def _init_mock_handlers(self) -> None:
        from backend.app.handlers import init_mock_handlers
        init_mock_handlers()

    def test_worker_throughput(self, bench_exec: str) -> None:
        """Run 100 mock tasks with 2 and 4 workers; verify 4 workers is faster."""
        from backend.app.engine.queue import enqueue_tasks, claim_task, complete_task
        from backend.app.db.connection import get_connection

        async def _run_with_workers(worker_count: int, task_count: int) -> float:
            conn = get_connection()
            conn.execute("DELETE FROM tasks WHERE execution_id = ?", (bench_exec,))
            conn.commit()

            tasks = [
                {
                    "id": f"wp-task-{i}",
                    "node_id": f"n{i}",
                    "kind": "textInput",
                    "label": f"Task {i}",
                    "config": {},
                    "depends_on": [],
                }
                for i in range(task_count)
            ]
            enqueue_tasks("wf-bench", bench_exec, tasks)

            start = time.perf_counter()

            async def _worker_loop(worker_id: int):
                while True:
                    task = claim_task(f"worker-{worker_id}", lease_seconds=30)
                    if task is None:
                        break
                    await asyncio.sleep(0.01)  # Simulate processing delay
                    complete_task(task["id"])

            worker_tasks = [
                asyncio.ensure_future(_worker_loop(w))
                for w in range(worker_count)
            ]
            await asyncio.gather(*worker_tasks)

            return time.perf_counter() - start

        loop = asyncio.new_event_loop()
        try:
            time_2w = loop.run_until_complete(_run_with_workers(2, 100))

            conn = get_connection()
            conn.execute("DELETE FROM tasks WHERE execution_id = ?", (bench_exec,))
            conn.commit()

            time_4w = loop.run_until_complete(_run_with_workers(4, 100))
        finally:
            loop.close()

        throughput_2w = 100 / time_2w if time_2w > 0 else 0
        throughput_4w = 100 / time_4w if time_4w > 0 else 0

        s = {
            "iterations": 1,
            "time_2_workers_s": round(time_2w, 4),
            "time_4_workers_s": round(time_4w, 4),
            "throughput_2_workers_tps": round(throughput_2w, 2),
            "throughput_4_workers_tps": round(throughput_4w, 2),
            "speedup": round(throughput_4w / throughput_2w, 2) if throughput_2w > 0 else 0,
        }

        faster = throughput_4w > throughput_2w
        get_collector().record(
            "worker.concurrency", s, category="worker",
            assertions=[
                f"4 workers ({throughput_4w:.1f} tps) faster than 2 workers ({throughput_2w:.1f} tps)",
            ],
            passed=faster,
        )
        assert faster, (
            f"4 workers ({throughput_4w:.1f} tps) should be faster than "
            f"2 workers ({throughput_2w:.1f} tps)"
        )


# ======================================================================
# 5. Memory Usage Benchmark
# ======================================================================


class TestMemoryBenchmark:
    """Benchmark memory usage during workflow operations."""

    def test_100_node_workflow_memory(self, memory_tracker: MemoryTracker) -> None:
        """Track peak memory while compiling a 100-node workflow.

        Asserts: Peak memory < 500 MB.
        """
        spec = generate_linear_workflow(100)

        memory_tracker.start()
        plan = compile_workflow(spec)
        stats = memory_tracker.stop()

        peak_mb = stats["peak_mb"]
        assert peak_mb < 500, f"Peak memory {peak_mb:.1f}MB >= 500MB"
        assert len(plan.tasks) == 100

        get_collector().record(
            "memory.workflow_100_node",
            {
                "iterations": 1,
                "peak_mb": stats["peak_mb"],
                "current_mb": stats["current_mb"],
                "total_tasks": len(plan.tasks),
            },
            category="memory",
            assertions=[
                f"Peak memory {peak_mb:.1f}MB < 500MB",
            ],
            passed=peak_mb < 500,
        )

    def test_50_node_diamond_memory(self, memory_tracker: MemoryTracker) -> None:
        """Track peak memory while compiling a 50-branch diamond workflow."""
        spec = generate_diamond_workflow(50)

        memory_tracker.start()
        plan = compile_workflow(spec)
        stats = memory_tracker.stop()

        get_collector().record(
            "memory.diamond_50",
            {
                "iterations": 1,
                "peak_mb": stats["peak_mb"],
                "current_mb": stats["current_mb"],
                "total_tasks": len(plan.tasks),
            },
            category="memory",
            assertions=[f"Peak memory {stats['peak_mb']:.1f}MB < 500MB"],
            passed=stats["peak_mb"] < 500,
        )
        assert stats["peak_mb"] < 500

    def test_large_task_creation_memory(self, memory_tracker: MemoryTracker) -> None:
        """Track memory when creating 10000 Task objects in an ExecutionPlan."""
        from backend.app.engine.compiler import ExecutionPlan, Task

        memory_tracker.start()
        tasks = [
            Task(
                id=f"t{i}",
                node_id=f"n{i}",
                node_kind="textInput",
                node_label=f"Task {i}",
                config={"data": "x" * 100},
            )
            for i in range(10_000)
        ]
        plan = ExecutionPlan(
            workflow_id="mem-stress",
            workflow_name="Memory Stress",
            tasks=tasks,
        )
        stats = memory_tracker.stop()

        get_collector().record(
            "memory.task_creation_10k",
            {
                "iterations": 1,
                "peak_mb": stats["peak_mb"],
                "current_mb": stats["current_mb"],
                "total_tasks": len(plan.tasks),
            },
            category="memory",
            assertions=[
                f"Peak memory for 10k tasks: {stats['peak_mb']:.1f}MB < 500MB",
            ],
            passed=stats["peak_mb"] < 500,
        )
        assert stats["peak_mb"] < 500
        assert len(plan.tasks) == 10_000
