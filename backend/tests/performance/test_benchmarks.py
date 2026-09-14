"""Performance tests — benchmarks for key operations."""

import time
import json
import pytest
from backend.app.engine.compiler import compile_workflow, topological_sort


class TestCompilerBenchmarks:
    """编译器性能基准。"""

    def _generate_linear_workflow(self, node_count: int) -> dict:
        """生成线性工作流。"""
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
                    "id": f"e{i-1}-{i}",
                    "source": f"n{i-1}",
                    "target": f"n{i}",
                    "type": "smoothstep",
                })
        return {"id": "bench", "name": "Benchmark", "nodes": nodes, "edges": edges}

    def _generate_diamond_workflow(self, width: int) -> dict:
        """生成菱形工作流。"""
        nodes = [
            {"id": "n0", "type": "studio", "position": {"x": 0, "y": 0},
             "data": {"label": "Start", "description": "", "kind": "textInput",
                      "outputType": "text", "config": {}}},
        ]
        edges = []

        # 中间层
        for i in range(width):
            nodes.append({
                "id": f"mid{i}", "type": "studio", "position": {"x": 200, "y": i * 100},
                "data": {"label": f"Mid {i}", "description": "", "kind": "textToImage",
                         "inputType": "text", "outputType": "image", "config": {}},
            })
            edges.append({"id": f"e0-mid{i}", "source": "n0", "target": f"mid{i}", "type": "smoothstep"})

        # 汇聚节点
        nodes.append({
            "id": "end", "type": "studio", "position": {"x": 400, "y": 0},
            "data": {"label": "End", "description": "", "kind": "output",
                     "inputType": "image", "config": {}},
        })
        for i in range(width):
            edges.append({"id": f"e-mid{i}-end", "source": f"mid{i}", "target": "end", "type": "smoothstep"})

        return {"id": "diamond", "name": "Diamond", "nodes": nodes, "edges": edges}

    def test_linear_100_nodes(self):
        """线性 100 节点编译。"""
        spec = self._generate_linear_workflow(100)
        start = time.time()
        plan = compile_workflow(spec)
        elapsed = time.time() - start

        assert len(plan.tasks) == 100
        assert elapsed < 0.1  # < 100ms

    def test_linear_500_nodes(self):
        """线性 500 节点编译。"""
        spec = self._generate_linear_workflow(500)
        start = time.time()
        plan = compile_workflow(spec)
        elapsed = time.time() - start

        assert len(plan.tasks) == 500
        assert elapsed < 0.5  # < 500ms

    def test_diamond_50_width(self):
        """菱形 50 宽度编译。"""
        spec = self._generate_diamond_workflow(50)
        start = time.time()
        plan = compile_workflow(spec)
        elapsed = time.time() - start

        assert len(plan.tasks) == 52  # 1 start + 50 mid + 1 end
        assert elapsed < 0.1

    def test_topological_sort_performance(self):
        """拓扑排序性能。"""
        # 创建大规模 DAG
        nodes = [{"id": f"n{i}", "data": {}} for i in range(1000)]
        edges = [{"id": f"e{i}", "source": f"n{i}", "target": f"n{i+1}"}
                 for i in range(999)]

        start = time.time()
        result = topological_sort(nodes, edges)
        elapsed = time.time() - start

        assert len(result) == 1000
        assert elapsed < 0.1


class TestQueueBenchmarks:
    """任务队列性能基准。"""

    def setup_method(self):
        from backend.app.db.connection import get_connection, init_db, close_connection
        import backend.app.db.connection as conn_module
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        conn_module._DB_PATH = f"{self.temp_dir}/bench.db"
        conn_module._CONNECTION = None
        close_connection()
        init_db()

        # 创建测试执行记录
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO workflows (id, name, schema_version, spec_json, version, created_at, updated_at) "
            "VALUES ('wf-bench', 'Bench', '1.0', '{}', 1, datetime('now'), datetime('now'))"
        )
        conn.execute(
            "INSERT INTO executions (id, workflow_id, workflow_snapshot, status, created_at) "
            "VALUES ('exec-bench', 'wf-bench', '{}', 'running', datetime('now'))"
        )
        conn.commit()

    def teardown_method(self):
        from backend.app.db.connection import close_connection
        import backend.app.db.connection as conn_module
        import shutil

        close_connection()
        conn_module._CONNECTION = None
        conn_module._DB_PATH = None
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_enqueue_1000_tasks(self):
        """入队 1000 个任务。"""
        from backend.app.engine.queue import enqueue_tasks

        tasks = [
            {"id": f"task-{i}", "node_id": f"n{i}", "kind": "textInput",
             "label": f"Task {i}", "config": {}, "depends_on": []}
            for i in range(1000)
        ]

        start = time.time()
        enqueue_tasks("wf-bench", "exec-bench", tasks)
        elapsed = time.time() - start

        assert elapsed < 1.0  # < 1s for 1000 tasks

    def test_sequential_claim_performance(self):
        """顺序领取性能。"""
        from backend.app.engine.queue import enqueue_tasks, claim_task, complete_task

        tasks = [
            {"id": f"task-{i}", "node_id": f"n{i}", "kind": "textInput",
             "label": f"Task {i}", "config": {}, "depends_on": []}
            for i in range(100)
        ]
        enqueue_tasks("wf-bench", "exec-bench", tasks)

        start = time.time()
        for _ in range(100):
            task = claim_task("worker-1", lease_seconds=30)
            if task:
                complete_task(task["id"])
        elapsed = time.time() - start

        assert elapsed < 2.0  # < 2s for 100 claim+complete cycles


class TestMemoryBenchmarks:
    """内存使用基准。"""

    def test_empty_workflow_memory(self):
        """空工作流内存使用。"""
        import sys
        from backend.app.engine.compiler import ExecutionPlan, Task

        # 创建大量 Task 对象
        tasks = [
            Task(id=f"t{i}", node_id=f"n{i}", node_kind="textInput",
                 node_label=f"Task {i}", config={})
            for i in range(10000)
        ]

        plan = ExecutionPlan(
            workflow_id="mem-test",
            workflow_name="Memory Test",
            tasks=tasks,
        )

        # 验证可以创建大量任务
        assert len(plan.tasks) == 10000
        assert plan.is_complete() is False  # 所有 pending
