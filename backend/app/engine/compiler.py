"""Graph Compiler — 将 WorkflowSpec 编译为可执行的 ExecutionPlan。

职责：
1. 拓扑排序（DAG 检测）
2. 失败传播标记
3. map_over 数组映射展开
4. 生成 Task 列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    """单个可执行任务。"""
    id: str
    node_id: str
    node_kind: str
    node_label: str
    item_key: str | None = None        # map 展开时的 scene_id / item 标识
    index: int = 0                     # map 展开时的序号
    config: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)  # 前置 task id 列表
    status: str = "pending"            # pending / running / completed / failed / skipped
    is_map_expansion: bool = False     # 是否为 map 展开的任务


@dataclass
class ExecutionPlan:
    """编译后的执行计划。"""
    workflow_id: str
    workflow_name: str
    tasks: list[Task]
    task_index: dict[str, Task] = field(default_factory=dict)  # task.id -> Task

    def __post_init__(self) -> None:
        self.task_index = {t.id: t for t in self.tasks}

    def get_ready_tasks(self) -> list[Task]:
        """返回所有依赖已完成、状态为 pending 的任务。"""
        ready = []
        for task in self.tasks:
            if task.status != "pending":
                continue
            deps = [self.task_index[d] for d in task.depends_on if d in self.task_index]
            if all(d.status == "completed" for d in deps):
                ready.append(task)
        return ready

    def mark_failed(self, task_id: str) -> list[str]:
        """标记任务失败，并传播到下游（blocked/skipped）。"""
        task = self.task_index.get(task_id)
        if not task:
            return []
        task.status = "failed"
        affected = []
        # 传播：所有依赖此任务的下游标记为 skipped
        for t in self.tasks:
            if task_id in t.depends_on and t.status == "pending":
                t.status = "skipped"
                affected.append(t.id)
        return affected

    def is_complete(self) -> bool:
        """检查所有任务是否已完成（含 skipped）。"""
        return all(t.status in ("completed", "skipped", "failed") for t in self.tasks)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for t in self.tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        return {"total": len(self.tasks), **counts}


class CompileError(Exception):
    """编译错误。"""


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Kahn 算法拓扑排序。检测环和悬空边。"""
    node_map = {n["id"]: n for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    children: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src not in node_map or tgt not in node_map:
            raise CompileError(f"边 {edge['id']} 引用了不存在的节点: {src} -> {tgt}")
        children[src].append(tgt)
        in_degree[tgt] = in_degree.get(tgt, 0) + 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    result: list[dict] = []

    while queue:
        nid = queue.pop(0)
        result.append(node_map[nid])
        for child in children[nid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(result) != len(nodes):
        remaining = set(n["id"] for n in nodes) - set(n["id"] for n in result)
        raise CompileError(f"检测到环形依赖，涉及节点: {remaining}")

    return result


def compile_workflow(spec: dict) -> ExecutionPlan:
    """将 WorkflowSpec 编译为 ExecutionPlan。"""
    nodes = spec.get("nodes", [])
    edges = spec.get("edges", [])

    if not nodes:
        raise CompileError("工作流没有任何节点")

    # 1. 拓扑排序
    sorted_nodes = topological_sort(nodes, edges)

    # 2. 预扫描：找到场景数量来源（storyboard 节点的 scenes 配置）
    global_scene_count = _find_scene_count_source(nodes)

    # 3. 构建边的依赖映射
    node_to_tasks: dict[str, list[str]] = {}  # node_id -> [task_ids]
    tasks: list[Task] = []

    for node in sorted_nodes:
        node_id = node["id"]
        data = node.get("data", {})
        kind = data.get("kind", "unknown")
        label = data.get("label", kind)
        config = data.get("config", {})
        map_over = config.get("mapOver", False)

        # 查找此节点的上游 task ids
        upstream_edges = [e for e in edges if e["target"] == node_id]
        upstream_task_ids = []
        for e in upstream_edges:
            upstream_task_ids.extend(node_to_tasks.get(e["source"], []))

        if map_over and kind in ("textToImage", "imageToVideo"):
            # map 展开：使用全局场景数量（从 storyboard 推断）
            scene_count = int(config.get("scenes", global_scene_count))
            for i in range(scene_count):
                scene_id = f"scene-{i + 1:03d}"
                task = Task(
                    id=f"{node_id}-{scene_id}",
                    node_id=node_id,
                    node_kind=kind,
                    node_label=label,
                    item_key=scene_id,
                    index=i,
                    config={**config, "scene_id": scene_id, "scene_index": i},
                    depends_on=list(upstream_task_ids),  # 依赖上游所有任务
                    is_map_expansion=True,
                )
                tasks.append(task)
            node_to_tasks[node_id] = [t.id for t in tasks if t.node_id == node_id]
        else:
            # 普通节点：单个任务
            task = Task(
                id=f"{node_id}-task",
                node_id=node_id,
                node_kind=kind,
                node_label=label,
                config=dict(config),
                depends_on=list(upstream_task_ids),
            )
            tasks.append(task)
            node_to_tasks[node_id] = [task.id]

    return ExecutionPlan(
        workflow_id=spec.get("id", ""),
        workflow_name=spec.get("name", ""),
        tasks=tasks,
    )


def _resolve_scene_count(config: dict, upstream_task_ids: list[str], tasks: list[Task]) -> int:
    """从配置或上游任务推断场景数量。"""
    if "scenes" in config:
        return int(config["scenes"])
    for t in tasks:
        if t.node_kind == "storyboard" and t.id in upstream_task_ids:
            return int(t.config.get("scenes", 5))
    return 5


def _find_scene_count_source(nodes: list[dict]) -> int:
    """从工作流节点中找到场景数量来源（通常是 storyboard 节点）。"""
    for node in nodes:
        data = node.get("data", {})
        if data.get("kind") == "storyboard":
            scenes = data.get("config", {}).get("scenes", 5)
            # scenes 可能是整数或列表
            if isinstance(scenes, list):
                return len(scenes)
            return int(scenes)
    return 5  # 默认


def expand_map_items(upstream_results: dict, node_config: dict) -> list[dict]:
    """根据上游 storyboard 实际输出动态创建 map item 列表。

    从 upstream_results 中提取 ``scenes`` 数组（位于
    ``result["output"]["metadata"]["scenes"]``），为每个 scene 生成一条
    map item dict（包含 scene_id、index、scene 元数据）。

    Args:
        upstream_results: 上游任务的执行结果映射 (task_id -> result dict)。
        node_config: 当前节点的配置（需要 ``mapOver: True`` 才生效）。

    Returns:
        按 scene.index 排序的 map item dict 列表。若上游无有效场景数据则
        返回空列表。
    """
    if not node_config.get("mapOver"):
        return []

    # 从上游结果中定位 scenes 列表
    scenes = _extract_scenes(upstream_results)

    if not scenes:
        return []

    items = []
    for scene in scenes:
        scene_id = scene.get("scene_id", f"scene-{scene.get('index', 0) + 1:03d}")
        items.append({
            "scene_id": scene_id,
            "index": scene.get("index", 0),
            "narration": scene.get("narration", ""),
            "image_prompt": scene.get("image_prompt", ""),
            "video_prompt": scene.get("video_prompt", ""),
            "duration_seconds": scene.get("duration_seconds", 5.0),
            "metadata": scene.get("metadata", {}),
        })

    items.sort(key=lambda x: x["index"])
    return items


def _extract_scenes(upstream_results: dict) -> list[dict]:
    """从上游任务结果中提取 scenes 列表。

    支持两种存储格式：
    1. ``result["output"]["metadata"]["scenes"]`` — NodeResult / ArtifactRef 序列化后的标准格式
    2. ``result["output"]["scenes"]`` — 旧的直接格式（兼容）
    3. ``result["scenes"]`` — 最外层直接存储（兼容）
    """
    for result in upstream_results.values():
        if not isinstance(result, dict):
            continue

        # 格式 1: NodeResult -> output.metadata.scenes
        output = result.get("output", {})
        if isinstance(output, dict):
            meta = output.get("metadata", {})
            if isinstance(meta, dict) and "scenes" in meta:
                return meta["scenes"]

            # 格式 2: output.scenes (legacy)
            if "scenes" in output:
                return output["scenes"]

        # 格式 3: result.scenes (flat)
        if "scenes" in result:
            return result["scenes"]

    return []
