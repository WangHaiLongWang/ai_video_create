# Performance Benchmarks

This document describes the performance benchmark suite for the `ai_video_create` backend and serves as a template for recording benchmark results.

## Running Benchmarks

```bash
cd backend

# Run all performance benchmarks
python -m pytest tests/performance/ -v --tb=short -m performance

# Run a specific benchmark category
python -m pytest tests/performance/ -v --tb=short -m performance -k "Compilation"
python -m pytest tests/performance/ -v --tb=short -m performance -k "Scheduler"
python -m pytest tests/performance/ -v --tb=short -m performance -k "APILatency"
python -m pytest tests/performance/ -v --tb=short -m performance -k "WorkerPool"
python -m pytest tests/performance/ -v --tb=short -m performance -k "Memory"

# Generate the benchmark report (requires running tests first)
python -c "
from backend.tests.performance.benchmark_reporter import get_collector
c = get_collector()
# (results are populated during test execution)
c.save_report('reports/performance-benchmark.md')
"
```

**Notes:**
- All benchmarks use mock providers; no real API calls are made.
- Each benchmark run uses an isolated SQLite database (in a temp directory).
- Timing uses `time.perf_counter()` for high-resolution measurements.
- Memory tracking uses Python's built-in `tracemalloc` module.

---

## Benchmark Categories

### 1. Workflow Compilation

Measures the time to compile a `WorkflowSpec` into an `ExecutionPlan`, including DAG validation and topological sort.

| Benchmark | Nodes | Topology | P95 Target |
|-----------|-------|----------|------------|
| `compile.linear_10` | 10 | Chain | < 100ms |
| `compile.linear_50` | 50 | Chain | < 100ms |
| `compile.linear_100` | 100 | Chain | < 100ms |
| `compile.diamond_50` | 52 | Fan-out/Fan-in | < 100ms |
| `compile.mixed_100` | 100 | Mixed DAG | < 100ms |
| `compile.topo_sort_1000` | 1000 | Chain | < 100ms |

### 2. Scheduler Throughput

Measures the scheduler's ability to identify ready tasks and process task completions.

| Benchmark | Tasks | Metric | Target |
|-----------|-------|--------|--------|
| `scheduler.schedule_10` | 10 | schedule_next_tasks | P95 < 100ms |
| `scheduler.schedule_50` | 50 | schedule_next_tasks | P95 < 100ms |
| `scheduler.schedule_100` | 100 | schedule_next_tasks | P95 < 200ms |
| `scheduler.completion_100` | 100 | claim+complete cycle | P95 < 2s |

### 3. API Latency

Measures response latency for common REST API endpoints using FastAPI TestClient.

| Benchmark | Endpoint | Target |
|-----------|----------|--------|
| `api.get_workflows` | GET /api/workflows | P95 < 100ms |
| `api.post_workflow` | POST /api/workflows | P95 < 100ms |
| `api.get_workflow_by_id` | GET /api/workflows/{id} | P95 < 100ms |
| `api.start_execution` | POST /api/executions/{id}/start | P95 < 100ms |
| `api.get_execution` | GET /api/executions/{id} | P95 < 100ms |

### 4. WorkerPool Concurrency

Measures task throughput with different worker pool sizes.

| Benchmark | Tasks | Workers | Assertion |
|-----------|-------|---------|-----------|
| `worker.concurrency` | 100 | 2 vs 4 | 4 workers throughput > 2 workers throughput |

Metrics reported:
- Wall-clock time per worker count
- Tasks per second (throughput)
- Speedup ratio

### 5. Memory Usage

Tracks peak memory consumption during workflow compilation and task creation.

| Benchmark | Operation | Target |
|-----------|-----------|--------|
| `memory.workflow_100_node` | Compile 100-node workflow | Peak < 500MB |
| `memory.diamond_50` | Compile 50-branch diamond | Peak < 500MB |
| `memory.task_creation_10k` | Create 10,000 Task objects | Peak < 500MB |

---

## Results Template

Fill in after each benchmark run:

### Run: [DATE]

**Environment:**
- Python version:
- OS:
- Hardware:

### Compilation Results

| Benchmark | Min (ms) | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Status |
|-----------|----------|----------|----------|----------|----------|--------|
| compile.linear_10 | | | | | | |
| compile.linear_50 | | | | | | |
| compile.linear_100 | | | | | | |
| compile.diamond_50 | | | | | | |
| compile.mixed_100 | | | | | | |
| compile.topo_sort_1000 | | | | | | |

### Scheduler Results

| Benchmark | Min (ms) | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Status |
|-----------|----------|----------|----------|----------|----------|--------|
| scheduler.schedule_10 | | | | | | |
| scheduler.schedule_50 | | | | | | |
| scheduler.schedule_100 | | | | | | |
| scheduler.completion_100 | | | | | | |

### API Latency Results

| Benchmark | Min (ms) | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Status |
|-----------|----------|----------|----------|----------|----------|--------|
| api.get_workflows | | | | | | |
| api.post_workflow | | | | | | |
| api.get_workflow_by_id | | | | | | |
| api.start_execution | | | | | | |
| api.get_execution | | | | | | |

### Worker Concurrency Results

| Metric | 2 Workers | 4 Workers |
|--------|-----------|-----------|
| Time (s) | | |
| Throughput (tasks/s) | | |
| Speedup | | |

### Memory Results

| Benchmark | Peak (MB) | Current (MB) | Status |
|-----------|-----------|--------------|--------|
| memory.workflow_100_node | | | |
| memory.diamond_50 | | | |
| memory.task_creation_10k | | | |

---

## Notes

- Benchmarks are **not** run in CI by default (marked with `@pytest.mark.performance`).
- To run in CI, add `-m performance` to the pytest command.
- The `BenchmarkCollector` saves results to `reports/performance-benchmark.md`.
- Historical results should be committed alongside code changes for tracking regressions.
