"""Node catalog loader — 基于 schemas/base-node-manifest.json 的单一事实来源。

HARD-101：冻结 base-node-manifest.json 后，后端所有消费方（图校验、agent tools、
模块端口校验、workflow factory）均应从本模块获取节点端口 id/type/cardinality，
不再各自手写重复表。

HARD-103 衔接点：删除残留的私有 port map（如 agent_tools 历史 _NODE_CATALOG_V2
手写表、workflow_factory.NODE_PORT_IDS 常量表）时，统一改为调用本模块。

文件路径约定：``<repo>/schemas/base-node-manifest.json``。可用环境变量
``AI_VIDEO_NODE_MANIFEST_PATH`` 覆盖（测试隔离用）。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from .node_manifest import (
    ExecutionHints,
    NodeManifest,
    PortDefinition,
    PortGroup,
)

# backend/app/schemas/node_catalog.py -> parents[3] = 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MANIFEST_PATH = _REPO_ROOT / "schemas" / "base-node-manifest.json"


def get_manifest_path() -> Path:
    """Resolve the shared base-node-manifest.json path."""
    override = os.environ.get("AI_VIDEO_NODE_MANIFEST_PATH", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_MANIFEST_PATH


@lru_cache(maxsize=1)
def _load_document() -> dict[str, Any]:
    """Load and cache the raw manifest document (schema + data)."""
    path = get_manifest_path()
    with path.open("r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"base-node-manifest must be an object: {path}")
    if "nodeKinds" not in doc:
        raise ValueError(f"base-node-manifest missing 'nodeKinds': {path}")
    return doc


def clear_cache() -> None:
    """Drop the cached document (tests that swap the manifest path)."""
    _load_document.cache_clear()
    load_node_catalog.cache_clear()


def load_manifest_document() -> dict[str, Any]:
    """Return the full shared document (JSON Schema $defs + nodeKinds data)."""
    return dict(_load_document())


def _port_from_dict(raw: dict[str, Any]) -> PortDefinition:
    return PortDefinition(
        id=raw["id"],
        type=raw["type"],
        required=bool(raw.get("required", False)),
        cardinality=raw.get("cardinality", "one"),
        label=raw.get("label"),
    )


def _manifest_from_dict(raw: dict[str, Any]) -> NodeManifest:
    ports = raw.get("ports") or {}
    execution = raw.get("execution")
    return NodeManifest(
        kind=raw["kind"],
        version=raw.get("version", "1.0.0"),
        category=raw["category"],
        label=raw["label"],
        description=raw.get("description", ""),
        ports=PortGroup(
            inputs=[_port_from_dict(p) for p in ports.get("inputs", [])],
            outputs=[_port_from_dict(p) for p in ports.get("outputs", [])],
        ),
        config_schema=raw.get("configSchema") or {},
        execution=ExecutionHints(**execution) if execution else None,
    )


@lru_cache(maxsize=1)
def load_node_catalog() -> dict[str, NodeManifest]:
    """Load all node manifests keyed by kind from the shared JSON."""
    doc = _load_document()
    catalog: dict[str, NodeManifest] = {}
    for raw in doc["nodeKinds"]:
        manifest = _manifest_from_dict(raw)
        if manifest.kind in catalog:
            raise ValueError(f"duplicate node kind in manifest: {manifest.kind}")
        catalog[manifest.kind] = manifest
    return catalog


def get_node_manifest(kind: str) -> NodeManifest | None:
    """Return the manifest for *kind*, or None when unknown."""
    return load_node_catalog().get(kind)


def list_node_manifests() -> list[NodeManifest]:
    """Return all manifests in catalog (file) order."""
    return list(load_node_catalog().values())


def list_node_kinds() -> list[str]:
    """Return all node kind strings in catalog order."""
    return list(load_node_catalog().keys())
