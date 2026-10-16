"""Shared fixtures for performance benchmark tests.

Provides:
- Workflow generation helpers of various sizes
- Isolated SQLite database setup/teardown per test
- Benchmark timing utilities
- Memory tracking via tracemalloc
"""

from __future__ import annotations

import gc
import os
import shutil
import tempfile
import time
import tracemalloc
from typing import Generator

import pytest


# ---------------------------------------------------------------------------
# Database isolation fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def bench_db() -> Generator[str, None, None]:
    """Create an isolated SQLite database for the duration of a test.

    Sets the global DB path used by ``backend.app.db.connection`` so that
    every test gets a clean database.  Tears down after the test finishes.
    """
    import backend.app.db.connection as conn_module
    from backend.app.db.connection import close_connection, init_db

    temp_dir = tempfile.mkdtemp(prefix="bench_db_")
    db_path = os.path.join(temp_dir, "bench.db")

    # Swap global state
    conn_module._DB_PATH = db_path
    conn_module._CONNECTION = None
    close_connection()
    init_db()

    yield db_path

    close_connection()
    conn_module._CONNECTION = None
    conn_module._DB_PATH = None
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture()
def bench_exec(bench_db: str) -> str:
    """Create a pre-seeded workflow + execution record, return execution_id."""
    from backend.app.db.connection import get_connection

    conn = get_connection()
    conn.execute(
        "INSERT INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
        "VALUES ('wf-bench', 'Bench', '1.0', '{}', 1, datetime('now'), datetime('now'))"
    )
    conn.execute(
        "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
        "VALUES ('exec-bench', 'wf-bench', '{}', 'running', datetime('now'))"
    )
    conn.commit()
    return "exec-bench"


# ---------------------------------------------------------------------------
# Workflow generation helpers
# ---------------------------------------------------------------------------

def generate_linear_workflow(node_count: int) -> dict:
    """Generate a purely linear (chain) workflow with *node_count* nodes.

    Node i depends on node i-1.
    """
    nodes = []
    edges = []
    for i in range(node_count):
        nodes.append({
            "id": f"n{i}",
            "type": "studio",
            "position": {"x": i * 200, "y": 0},
            "data": {
                "label": f"Node {i}",
                "description": f"Node {i}",
                "kind": "textInput" if i == 0 else "textToImage",
                "inputType": "text" if i > 0 else None,
                "outputType": "text" if i < node_count - 1 else None,
                "config": {},
            },
        })
        if i > 0:
            edges.append({
                "id": f"e{i - 1}-{i}",
                "source": f"n{i - 1}",
                "target": f"n{i}",
                "type": "smoothstep",
            })
    return {"id": "bench-linear", "name": "Linear Benchmark", "nodes": nodes, "edges": edges}


def generate_diamond_workflow(width: int) -> dict:
    """Generate a diamond (fan-out / fan-in) workflow.

    One start node fans out to *width* parallel middle nodes, which converge
    into a single end node.  Total nodes = width + 2.
    """
    nodes = [
        {
            "id": "n0", "type": "studio", "position": {"x": 0, "y": 0},
            "data": {
                "label": "Start", "description": "", "kind": "textInput",
                "outputType": "text", "config": {},
            },
        },
    ]
    edges = []

    for i in range(width):
        nodes.append({
            "id": f"mid{i}",
            "type": "studio",
            "position": {"x": 200, "y": i * 100},
            "data": {
                "label": f"Mid {i}",
                "description": "",
                "kind": "textToImage",
                "inputType": "text",
                "outputType": "image",
                "config": {},
            },
        })
        edges.append({
            "id": f"e0-mid{i}", "source": "n0", "target": f"mid{i}", "type": "smoothstep",
        })

    nodes.append({
        "id": "end", "type": "studio", "position": {"x": 400, "y": 0},
        "data": {
            "label": "End", "description": "", "kind": "output",
            "inputType": "image", "config": {},
        },
    })
    for i in range(width):
        edges.append({
            "id": f"e-mid{i}-end", "source": f"mid{i}", "target": "end", "type": "smoothstep",
        })

    return {"id": "bench-diamond", "name": "Diamond Benchmark", "nodes": nodes, "edges": edges}


def generate_mixed_dag(node_count: int) -> dict:
    """Generate a mixed DAG where ~30 % of nodes have fan-out edges.

    The graph is constructed so that node *i* may fan out to up to 3
    subsequent nodes, producing a realistic mix of sequential and parallel
    paths.  No cycles are created.
    """
    import random
    random.seed(42)  # reproducible

    nodes = []
    edges = []
    for i in range(node_count):
        kind = "textInput" if i == 0 else ("textToImage" if i % 3 != 0 else "imageToVideo")
        nodes.append({
            "id": f"n{i}",
            "type": "studio",
            "position": {"x": (i % 20) * 200, "y": (i // 20) * 100},
            "data": {
                "label": f"Node {i}",
                "description": f"Node {i}",
                "kind": kind,
                "inputType": "text",
                "outputType": "image",
                "config": {},
            },
        })

    # Build edges: each node (except last) connects to 1-3 successors
    for i in range(node_count - 1):
        fan = random.randint(1, 3)
        targets = []
        for offset in range(1, min(fan + 1, node_count - i)):
            t = i + offset
            if t < node_count:
                targets.append(t)
        for t in targets:
            edges.append({
                "id": f"e{i}-{t}", "source": f"n{i}", "target": f"n{t}", "type": "smoothstep",
            })

    return {"id": "bench-mixed", "name": "Mixed DAG Benchmark", "nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Benchmark timing fixtures
# ---------------------------------------------------------------------------

class BenchmarkTimer:
    """Collects multiple timing samples and computes statistics."""

    def __init__(self, iterations: int = 20) -> None:
        self.iterations = iterations
        self.samples: list[float] = []

    def run(self, fn, *args, **kwargs):  # noqa: ANN002
        """Execute *fn* multiple times and record durations (seconds)."""
        self.samples.clear()
        for _ in range(self.iterations):
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            elapsed = time.perf_counter() - start
            self.samples.append(elapsed)
        return result

    # -- statistics --------------------------------------------------------

    @property
    def min(self) -> float:  # noqa: A002
        return min(self.samples) if self.samples else 0.0

    @property
    def max(self) -> float:  # noqa: A002
        return max(self.samples) if self.samples else 0.0

    @property
    def avg(self) -> float:
        return sum(self.samples) / len(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    def percentile(self, p: float) -> float:
        """Return the *p*-th percentile (0-100) of collected samples."""
        if not self.samples:
            return 0.0
        sorted_s = sorted(self.samples)
        k = (len(sorted_s) - 1) * (p / 100)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_s) else f
        return sorted_s[f] + (k - f) * (sorted_s[c] - sorted_s[f])

    def summary(self) -> dict:
        return {
            "iterations": self.iterations,
            "min_s": round(self.min, 6),
            "max_s": round(self.max, 6),
            "avg_s": round(self.avg, 6),
            "p50_s": round(self.percentile(50), 6),
            "p95_s": round(self.percentile(95), 6),
            "p99_s": round(self.percentile(99), 6),
        }


@pytest.fixture()
def benchmark_timer() -> BenchmarkTimer:
    """Provide a fresh BenchmarkTimer with 30 iterations."""
    return BenchmarkTimer(iterations=30)


# ---------------------------------------------------------------------------
# Memory tracking fixture
# ---------------------------------------------------------------------------

class MemoryTracker:
    """Wrapper around ``tracemalloc`` for benchmark memory reporting."""

    def start(self) -> None:
        gc.collect()
        tracemalloc.start()

    def stop(self) -> dict:
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return {
            "current_bytes": current,
            "peak_bytes": peak,
            "current_mb": round(current / (1024 * 1024), 2),
            "peak_mb": round(peak / (1024 * 1024), 2),
        }


@pytest.fixture()
def memory_tracker() -> MemoryTracker:
    """Provide a MemoryTracker instance."""
    return MemoryTracker()
