"""Performance benchmarks for module operations.

Ensures that critical module-system operations complete within acceptable
time thresholds even at realistic scale (100+ modules, 20-node workflows,
concurrent access).

All benchmarks use time.perf_counter() for high-resolution timing and run
multiple iterations to produce stable averages.
"""

from __future__ import annotations

import time
import concurrent.futures
from typing import Any

import pytest

from backend.app.schemas.module_definition import ModuleDefinition, ProviderPolicy
from backend.app.schemas.node_manifest import ExecutionHints
from backend.app.services.module_registry import ModuleRegistry
from backend.app.services.module_diff import compute_module_diff
from backend.app.services.module_port_validator import PortBindingValidator
from backend.app.services.execution_resolver import ExecutionResolver


# ---------------------------------------------------------------------------
# Test data generators
# ---------------------------------------------------------------------------

# Valid baseKinds from _NODE_CATALOG_V2
_BASE_KINDS = ["textInput", "storyboard", "textToImage", "imageToVideo", "videoConcat", "output"]

_CATEGORIES = ["input", "generator", "image", "video", "compositor", "output"]

_CAPABILITIES = ["text", "image", "video"]

_PROVIDERS = ["doubao", "openai", "runway", "kling", "pika", "suno"]

_PORT_TEMPLATES: dict[str, dict[str, list[dict[str, Any]]]] = {
    "textInput": {
        "inputs": [],
        "outputs": [{"id": "text", "type": "text", "required": True, "cardinality": "one"}],
    },
    "storyboard": {
        "inputs": [{"id": "prompt", "type": "text", "required": True, "cardinality": "one"}],
        "outputs": [{"id": "scenes", "type": "scene", "required": True, "cardinality": "many"}],
    },
    "textToImage": {
        "inputs": [{"id": "scene", "type": "scene", "required": True, "cardinality": "one"}],
        "outputs": [{"id": "image", "type": "image", "required": True, "cardinality": "one"}],
    },
    "imageToVideo": {
        "inputs": [{"id": "image", "type": "image", "required": True, "cardinality": "one"}],
        "outputs": [{"id": "video", "type": "video", "required": True, "cardinality": "many"}],
    },
    "videoConcat": {
        "inputs": [{"id": "video", "type": "video", "required": True, "cardinality": "many"}],
        "outputs": [{"id": "video", "type": "video", "required": True, "cardinality": "one"}],
    },
    "output": {
        "inputs": [{"id": "video", "type": "video", "required": True, "cardinality": "one"}],
        "outputs": [],
    },
}


def _make_module(index: int, base_kind: str | None = None) -> ModuleDefinition:
    """Create a realistic ModuleDefinition with varied fields."""
    bk = base_kind or _BASE_KINDS[index % len(_BASE_KINDS)]
    cat = _CATEGORIES[index % len(_CATEGORIES)]
    cap = _CAPABILITIES[index % len(_CAPABILITIES)]
    provider = _PROVIDERS[index % len(_PROVIDERS)]
    ports = _PORT_TEMPLATES[bk]

    return ModuleDefinition(
        id=f"bench.module.{index:04d}",
        version="1.0.0",
        status="published",
        baseKind=bk,
        category=cat,
        label=f"Benchmark Module {index}",
        description=f"Auto-generated benchmark module #{index} for performance testing",
        icon="puzzle-piece",
        providerPolicy=ProviderPolicy(
            capability=cap,
            allowed=[provider, "doubao"],
            default=provider,
            locked=index % 3 == 0,
        ),
        configSchema={
            "properties": {
                "model": {"type": "string", "title": "Model", "default": f"model-{index}"},
                "temperature": {"type": "number", "title": "Temperature", "default": 0.7},
                "max_tokens": {"type": "integer", "title": "Max Tokens", "default": 1024},
                "variantCount": {"type": "integer", "title": "Variants", "default": 1},
            },
            "required": ["model"],
        },
        defaultConfig={
            "provider": provider,
            "model": f"model-{index}",
            "temperature": 0.7,
        },
        ports=ports,
        execution=ExecutionHints(mapOver="scene") if bk == "textToImage" else None,
        metadata={"builtin": False, "author": "bench", "index": index},
    )


def _make_module_v2(index: int, base_kind: str | None = None) -> ModuleDefinition:
    """Create a second version of a module with some changes for diff testing."""
    v1 = _make_module(index, base_kind)
    # Make some changes to create a meaningful diff
    return ModuleDefinition(
        id=v1.id,
        version="2.0.0",
        status="published",
        baseKind=v1.base_kind,
        category=v1.category,
        label=f"{v1.label} v2",
        description=f"{v1.description} (updated)",
        icon=v1.icon,
        providerPolicy=ProviderPolicy(
            capability=v1.provider_policy.capability,
            allowed=v1.provider_policy.allowed[:1],  # restrict providers
            default=v1.provider_policy.default,
            locked=True,
        ),
        configSchema={
            "properties": {
                "model": {"type": "string", "title": "Model", "default": f"model-{index}-v2"},
                "temperature": {"type": "number", "title": "Temperature", "default": 0.5},
                "max_tokens": {"type": "integer", "title": "Max Tokens", "default": 2048},
                "variantCount": {"type": "integer", "title": "Variants", "default": 2},
                "new_field": {"type": "string", "title": "New Field", "default": "added"},
            },
            "required": ["model"],
        },
        defaultConfig=v1.default_config,
        ports=v1.ports,
        execution=v1.execution,
        metadata=v1.metadata,
    )


def _build_registry_with_n(n: int) -> tuple[ModuleRegistry, list[ModuleDefinition]]:
    """Build a registry pre-loaded with n modules and return both."""
    registry = ModuleRegistry()
    modules = []
    for i in range(n):
        m = _make_module(i)
        modules.append(m)
        # Inject directly into the registry's internal store (bypass DB)
        registry._modules.setdefault(m.id, {})[m.version] = m
    return registry, modules


def _build_workflow_spec(module_ids: list[str], total_nodes: int = 20) -> dict:
    """Build a workflow spec with total_nodes, module_ids referenced by some nodes."""
    nodes = []
    for i in range(total_nodes):
        if i < len(module_ids):
            mid = module_ids[i % len(module_ids)]
            nodes.append({
                "id": f"node-{i}",
                "data": {
                    "kind": "textToImage",
                    "moduleId": mid,
                    "moduleVersion": "1.0.0",
                    "configOverrides": {"temperature": 0.8},
                },
            })
        else:
            nodes.append({
                "id": f"node-{i}",
                "data": {
                    "kind": "textInput",
                    "config": {"prompt": f"Scene {i}"},
                },
            })
    return {"id": "bench-workflow", "nodes": nodes}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bench(fn, iterations: int = 50) -> float:
    """Run fn() for `iterations` and return average wall-clock seconds."""
    for _ in range(2):
        fn()  # warm-up
    total = 0.0
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        total += time.perf_counter() - start
    return total / iterations


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


class TestModulePerformance:
    """Performance benchmarks for module operations."""

    # ------------------------------------------------------------------
    # 1. Registry list_modules with 100 modules
    # ------------------------------------------------------------------

    def test_registry_list_100_modules(self):
        """Listing 100 modules should complete in < 100ms."""
        registry, _ = _build_registry_with_n(100)

        avg = _bench(lambda: registry.list_modules(), iterations=100)
        ms = avg * 1000
        print(f"\n  [BENCH] list_modules (100 modules): {ms:.2f} ms avg")
        assert avg < 0.100, f"list_modules too slow: {ms:.2f}ms (threshold: 100ms)"

    # ------------------------------------------------------------------
    # 2. Registry get_module
    # ------------------------------------------------------------------

    def test_registry_get_module(self):
        """Getting a single module should complete in < 10ms."""
        registry, _ = _build_registry_with_n(100)

        avg = _bench(lambda: registry.get_module("bench.module.0050"), iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] get_module: {ms:.2f} ms avg")
        assert avg < 0.010, f"get_module too slow: {ms:.2f}ms (threshold: 10ms)"

    # ------------------------------------------------------------------
    # 3. Search/filter 100 modules by capability
    # ------------------------------------------------------------------

    def test_search_filter_100_modules(self):
        """Filtering 100 modules by capability should complete in < 50ms."""
        registry, _ = _build_registry_with_n(100)

        avg = _bench(lambda: registry.list_modules(capability="image"), iterations=100)
        ms = avg * 1000
        print(f"\n  [BENCH] list_modules(capability='image', 100 modules): {ms:.2f} ms avg")
        assert avg < 0.050, f"search filter too slow: {ms:.2f}ms (threshold: 50ms)"

    # ------------------------------------------------------------------
    # 4. Validate module definition
    # ------------------------------------------------------------------

    def test_validate_module_definition(self):
        """Validating a module definition should complete in < 50ms."""
        registry = ModuleRegistry()
        module = _make_module(0)

        avg = _bench(lambda: registry.validate_module(module), iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] validate_module: {ms:.2f} ms avg")
        assert avg < 0.050, f"validate_module too slow: {ms:.2f}ms (threshold: 50ms)"

    # ------------------------------------------------------------------
    # 5. Port binding validation
    # ------------------------------------------------------------------

    def test_port_binding_validation(self):
        """Validating port bindings should complete in < 20ms."""
        validator = PortBindingValidator()
        module = _make_module(0)

        avg = _bench(lambda: validator.validate_ports(module), iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] validate_ports: {ms:.2f} ms avg")
        assert avg < 0.020, f"validate_ports too slow: {ms:.2f}ms (threshold: 20ms)"

    # ------------------------------------------------------------------
    # 6. Module diff computation
    # ------------------------------------------------------------------

    def test_module_diff_computation(self):
        """Computing diff between two versions should complete in < 50ms."""
        old = _make_module(0)
        new = _make_module_v2(0)

        avg = _bench(lambda: compute_module_diff(old, new), iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] compute_module_diff: {ms:.2f} ms avg")
        assert avg < 0.050, f"compute_module_diff too slow: {ms:.2f}ms (threshold: 50ms)"

    # ------------------------------------------------------------------
    # 7. Execution resolver with 10 module nodes
    # ------------------------------------------------------------------

    def test_execution_resolver_with_10_modules(self):
        """Resolving config for 10 module nodes should complete in < 200ms."""
        registry, modules = _build_registry_with_n(20)
        module_ids = [m.id for m in modules[:10]]
        spec = _build_workflow_spec(module_ids, total_nodes=10)
        resolver = ExecutionResolver(registry=registry)

        avg = _bench(lambda: resolver.resolve_workflow(spec), iterations=50)
        ms = avg * 1000
        print(f"\n  [BENCH] resolve_workflow (10 module nodes): {ms:.2f} ms avg")
        assert avg < 0.200, f"resolve_workflow too slow: {ms:.2f}ms (threshold: 200ms)"

    # ------------------------------------------------------------------
    # 8. Concurrent reads
    # ------------------------------------------------------------------

    def test_concurrent_reads(self):
        """100 concurrent reads of module registry should complete in < 1s."""
        registry, _ = _build_registry_with_n(100)

        def _read_module(module_idx: int) -> ModuleDefinition | None:
            return registry.get_module(f"bench.module.{module_idx:04d}")

        start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            futures = [pool.submit(_read_module, i) for i in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.perf_counter() - start
        ms = elapsed * 1000
        print(f"\n  [BENCH] 100 concurrent reads: {ms:.2f} ms total")
        assert all(r is not None for r in results), "Some concurrent reads returned None"
        assert elapsed < 1.0, f"concurrent reads too slow: {ms:.2f}ms (threshold: 1000ms)"

    # ------------------------------------------------------------------
    # 9. Parser with module prompt (mock)
    # ------------------------------------------------------------------

    def test_parser_with_module_prompt(self):
        """Parsing a prompt with module references should complete in < 500ms (mock)."""
        # Simulate parsing cost by building and querying a large registry
        # In production this would be LLM-backed; here we benchmark the
        # pure-data path: list modules, filter, resolve config for each.
        registry, modules = _build_registry_with_n(100)
        module_ids = [m.id for m in modules[:20]]

        def _simulate_parse():
            # Step 1: list all modules
            all_mods = registry.list_modules()
            # Step 2: filter by capability
            image_mods = registry.list_modules(capability="image")
            # Step 3: resolve config for each referenced module
            for mid in module_ids:
                registry.resolve_effective_config(mid, {"temperature": 0.9})
            return len(all_mods), len(image_mods)

        avg = _bench(_simulate_parse, iterations=20)
        ms = avg * 1000
        print(f"\n  [BENCH] parser simulation (100 modules, 20 resolve): {ms:.2f} ms avg")
        assert avg < 0.500, f"parser simulation too slow: {ms:.2f}ms (threshold: 500ms)"

    # ------------------------------------------------------------------
    # 10. Dependency extraction from 20-node workflow
    # ------------------------------------------------------------------

    def test_dependency_extraction(self):
        """Extracting dependencies from a 20-node workflow should complete in < 50ms."""
        registry, modules = _build_registry_with_n(20)
        module_ids = [m.id for m in modules[:10]]
        spec = _build_workflow_spec(module_ids, total_nodes=20)

        def _extract_deps():
            # Walk all nodes and collect module dependencies
            deps: dict[str, str] = {}
            for node in spec.get("nodes", []):
                data = node.get("data", {})
                mid = data.get("moduleId")
                if mid:
                    version = data.get("moduleVersion", "latest")
                    deps[node["id"]] = f"{mid}@{version}"
            return deps

        avg = _bench(_extract_deps, iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] dependency extraction (20 nodes): {ms:.2f} ms avg")
        assert avg < 0.050, f"dependency extraction too slow: {ms:.2f}ms (threshold: 50ms)"


# ---------------------------------------------------------------------------
# Scale stress test (bonus)
# ---------------------------------------------------------------------------


class TestModuleScaleStress:
    """Stress tests at higher module counts to catch O(n^2) regressions."""

    def test_list_500_modules(self):
        """Listing 500 modules should complete in < 500ms."""
        registry, _ = _build_registry_with_n(500)

        avg = _bench(lambda: registry.list_modules(), iterations=20)
        ms = avg * 1000
        print(f"\n  [BENCH] list_modules (500 modules): {ms:.2f} ms avg")
        assert avg < 0.500, f"list_modules(500) too slow: {ms:.2f}ms (threshold: 500ms)"

    def test_get_module_from_500(self):
        """Getting a single module from 500 should complete in < 20ms."""
        registry, _ = _build_registry_with_n(500)

        avg = _bench(lambda: registry.get_module("bench.module.0250"), iterations=200)
        ms = avg * 1000
        print(f"\n  [BENCH] get_module (from 500): {ms:.2f} ms avg")
        assert avg < 0.020, f"get_module(500) too slow: {ms:.2f}ms (threshold: 20ms)"

    def test_validate_100_modules_sequentially(self):
        """Validating 100 modules sequentially should complete in < 2s."""
        registry = ModuleRegistry()
        modules = [_make_module(i) for i in range(100)]

        start = time.perf_counter()
        for m in modules:
            registry.validate_module(m)
        elapsed = time.perf_counter() - start
        ms = elapsed * 1000
        print(f"\n  [BENCH] validate 100 modules sequentially: {ms:.2f} ms total")
        assert elapsed < 2.0, f"validate 100 sequential too slow: {ms:.2f}ms (threshold: 2000ms)"
