"""Comprehensive tests for backend authoritative graph validation service.

Covers:
  - SELF_LOOP
  - DUPLICATE_EDGE
  - TYPE_MISMATCH
  - CARDINALITY_VIOLATION
  - REQUIRED_PORT
  - CYCLE
  - DIRECTION (output->output, input->input)
  - UNKNOWN_NODE_KIND (node kind not in catalog)
  - UNKNOWN_HANDLE (handle references non-existent port)
  - Valid graph (no errors)
  - HTTPException422 structured envelope
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.domain.graph_validation import (
    build_422_response,
    extract_nodes_edges_from_spec,
    get_node_catalog,
    raise_if_invalid,
    validate_graph,
)
from backend.app.schemas.graph_validator import GraphValidationError
from backend.app.schemas.node_manifest import (
    NodeManifest,
    PortDefinition,
    PortGroup,
)


# ---------------------------------------------------------------------------
# Test catalog -- a minimal subset of the real catalog for deterministic tests
# ---------------------------------------------------------------------------

TEST_CATALOG: dict[str, NodeManifest] = {
    "textInput": NodeManifest(
        kind="textInput",
        category="input",
        label="TextInput",
        ports=PortGroup(
            inputs=[],
            outputs=[
                PortDefinition(id="text", type="text", required=True),
            ],
        ),
    ),
    "storyboard": NodeManifest(
        kind="storyboard",
        category="generator",
        label="Storyboard",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="prompt", type="text", required=True, cardinality="one"),
            ],
            outputs=[
                PortDefinition(id="scenes", type="scene", required=True, cardinality="many"),
            ],
        ),
    ),
    "textToImage": NodeManifest(
        kind="textToImage",
        category="generator",
        label="TextToImage",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="scene", type="scene", required=True, cardinality="one"),
            ],
            outputs=[
                PortDefinition(id="image", type="image", required=True, cardinality="one"),
            ],
        ),
    ),
    "imageToVideo": NodeManifest(
        kind="imageToVideo",
        category="video",
        label="ImageToVideo",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="image", type="image", required=True, cardinality="one"),
            ],
            outputs=[
                PortDefinition(id="video", type="video", required=True, cardinality="many"),
            ],
        ),
    ),
    "videoConcat": NodeManifest(
        kind="videoConcat",
        category="compositor",
        label="VideoConcat",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="video", type="video", required=True, cardinality="many"),
            ],
            outputs=[
                PortDefinition(id="video", type="video", required=True),
            ],
        ),
    ),
    "output": NodeManifest(
        kind="output",
        category="output",
        label="Output",
        ports=PortGroup(
            inputs=[
                PortDefinition(id="video", type="video", required=True, cardinality="one"),
            ],
            outputs=[],
        ),
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(id: str, kind: str) -> dict:
    return {"id": id, "kind": kind}


def _data_node(id: str, kind: str, ports: dict | None = None, module_id: str | None = None, module_version: str | None = None) -> dict:
    """Build a node carrying instance-level data (module-aware)."""
    data: dict = {"kind": kind}
    if ports is not None:
        data["ports"] = ports
    if module_id is not None:
        data["moduleId"] = module_id
    if module_version is not None:
        data["moduleVersion"] = module_version
    return {"id": id, "kind": kind, "data": data}


def _edge(id: str, source: str, target: str, sourceHandle: str | None = None, targetHandle: str | None = None) -> dict:
    e = {"id": id, "source": source, "target": target}
    if sourceHandle is not None:
        e["sourceHandle"] = sourceHandle
    if targetHandle is not None:
        e["targetHandle"] = targetHandle
    return e


# ---------------------------------------------------------------------------
# Tests: SELF_LOOP
# ---------------------------------------------------------------------------

class TestSelfLoop:
    def test_self_loop_detected(self):
        nodes = [_node("a", "textInput")]
        edges = [_edge("e1", "a", "a", "text", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "SELF_LOOP" in codes

    def test_self_loop_error_message(self):
        nodes = [_node("a", "textInput")]
        edges = [_edge("e1", "a", "a", "text", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        self_loop = [e for e in errors if e.code == "SELF_LOOP"][0]
        assert "e1" in self_loop.message
        assert self_loop.edge_id == "e1"


# ---------------------------------------------------------------------------
# Tests: DUPLICATE_EDGE
# ---------------------------------------------------------------------------

class TestDuplicateEdge:
    def test_duplicate_edge_detected(self):
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [
            _edge("e1", "a", "b", "text", "prompt"),
            _edge("e2", "a", "b", "text", "prompt"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "DUPLICATE_EDGE" in codes

    def test_different_handles_not_duplicate(self):
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [
            _edge("e1", "a", "b", "text", "prompt"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        # No duplicate
        assert not any(e.code == "DUPLICATE_EDGE" for e in errors)


# ---------------------------------------------------------------------------
# Tests: TYPE_MISMATCH
# ---------------------------------------------------------------------------

class TestTypeMismatch:
    def test_type_mismatch_detected(self):
        # textInput(text) -> output(video) -- type mismatch
        nodes = [_node("a", "textInput"), _node("b", "output")]
        edges = [_edge("e1", "a", "b", "text", "video")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "TYPE_MISMATCH" in codes

    def test_compatible_types_no_error(self):
        # textInput(text) -> storyboard(prompt:text) -- compatible
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "text", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "TYPE_MISMATCH" for e in errors)


# ---------------------------------------------------------------------------
# Tests: CARDINALITY_VIOLATION
# ---------------------------------------------------------------------------

class TestCardinalityViolation:
    def test_cardinality_one_violation(self):
        # storyboard.scenes(cardinality=many) connects to textToImage.scene(cardinality=one)
        # But we send two edges into textToImage.scene
        nodes = [
            _node("s1", "storyboard"),
            _node("s2", "storyboard"),
            _node("ti", "textToImage"),
        ]
        edges = [
            _edge("e1", "s1", "ti", "scenes", "scene"),
            _edge("e2", "s2", "ti", "scenes", "scene"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "CARDINALITY_VIOLATION" in codes

    def test_cardinality_many_no_violation(self):
        # videoConcat.videos(cardinality=many) -- multiple edges OK
        nodes = [
            _node("v1", "imageToVideo"),
            _node("v2", "imageToVideo"),
            _node("vc", "videoConcat"),
        ]
        edges = [
            _edge("e1", "v1", "vc", "video", "video"),
            _edge("e2", "v2", "vc", "video", "video"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "CARDINALITY_VIOLATION" for e in errors)


# ---------------------------------------------------------------------------
# Tests: REQUIRED_PORT
# ---------------------------------------------------------------------------

class TestRequiredPort:
    def test_required_port_unconnected(self):
        # storyboard has required input "prompt" but no edge connected
        nodes = [_node("sb", "storyboard")]
        edges = []
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "REQUIRED_PORT" in codes

    def test_required_port_connected(self):
        nodes = [_node("ti", "textInput"), _node("sb", "storyboard")]
        edges = [_edge("e1", "ti", "sb", "text", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        # storyboard.prompt is connected, no required_port error for it
        required_errors = [e for e in errors if e.code == "REQUIRED_PORT" and e.node_id == "sb"]
        assert len(required_errors) == 0


# ---------------------------------------------------------------------------
# Tests: CYCLE
# ---------------------------------------------------------------------------

class TestCycle:
    def test_cycle_detected(self):
        nodes = [
            _node("a", "storyboard"),
            _node("b", "textToImage"),
            _node("c", "imageToVideo"),
        ]
        edges = [
            _edge("e1", "a", "b", "scenes", "scene"),
            _edge("e2", "b", "c", "image", "image"),
            _edge("e3", "c", "a", "video", "prompt"),  # back edge -- creates cycle
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "CYCLE" in codes

    def test_dag_no_cycle(self):
        nodes = [
            _node("a", "textInput"),
            _node("b", "storyboard"),
            _node("c", "textToImage"),
        ]
        edges = [
            _edge("e1", "a", "b", "text", "prompt"),
            _edge("e2", "b", "c", "scenes", "scene"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "CYCLE" for e in errors)


# ---------------------------------------------------------------------------
# Tests: DIRECTION
# ---------------------------------------------------------------------------

class TestDirection:
    def test_direction_from_input_port(self):
        # Connecting from storyboard's input port "prompt" as source handle
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "text", "prompt")]
        # This is valid: text (output) -> prompt (input)
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        direction_errors = [e for e in errors if e.code == "DIRECTION"]
        assert len(direction_errors) == 0

    def test_direction_into_output_port(self):
        # Connecting into storyboard's output port "scenes"
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "text", "scenes")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = [e.code for e in errors]
        # "scenes" is an output port on storyboard, so connecting INTO it is wrong
        assert "DIRECTION" in codes


# ---------------------------------------------------------------------------
# Tests: Valid graph
# ---------------------------------------------------------------------------

class TestValidGraph:
    def test_full_pipeline_no_errors(self):
        nodes = [
            _node("ti", "textInput"),
            _node("sb", "storyboard"),
            _node("tti", "textToImage"),
            _node("itv", "imageToVideo"),
            _node("vc", "videoConcat"),
            _node("out", "output"),
        ]
        edges = [
            _edge("e1", "ti", "sb", "text", "prompt"),
            _edge("e2", "sb", "tti", "scenes", "scene"),
            _edge("e3", "tti", "itv", "image", "image"),
            _edge("e4", "itv", "vc", "video", "video"),
            _edge("e5", "vc", "out", "video", "video"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert errors == [], f"Expected no errors but got: {errors}"

    def test_empty_graph_valid(self):
        errors = validate_graph([], [], TEST_CATALOG)
        assert errors == []


# ---------------------------------------------------------------------------
# Tests: extract_nodes_edges_from_spec
# ---------------------------------------------------------------------------

class TestExtractNodesEdges:
    def test_v1_format(self):
        spec = {
            "nodes": [
                {"id": "a", "data": {"kind": "textInput"}, "position": {"x": 0, "y": 0}},
            ],
            "edges": [
                {"id": "e1", "source": "a", "target": "b"},
            ],
        }
        nodes, edges = extract_nodes_edges_from_spec(spec)
        assert len(nodes) == 1
        assert nodes[0]["data"]["kind"] == "textInput"
        assert len(edges) == 1

    def test_v2_format(self):
        spec = {
            "nodes": [{"id": "a", "kind": "textInput"}],
            "edges": [{"id": "e1", "source": "a", "target": "b"}],
        }
        nodes, edges = extract_nodes_edges_from_spec(spec)
        assert len(nodes) == 1
        assert nodes[0]["kind"] == "textInput"


# ---------------------------------------------------------------------------
# Tests: raise_if_invalid
# ---------------------------------------------------------------------------

class TestRaiseIfInvalid:
    def test_raises_422_on_invalid_graph(self):
        nodes = [_node("a", "textInput"), _node("b", "output")]
        edges = [_edge("e1", "a", "b", "text", "video")]
        with pytest.raises(HTTPException) as exc_info:
            raise_if_invalid(nodes, edges, TEST_CATALOG)
        assert exc_info.value.status_code == 422

    def test_422_detail_structure(self):
        nodes = [_node("a", "textInput"), _node("b", "output")]
        edges = [_edge("e1", "a", "b", "text", "video")]
        with pytest.raises(HTTPException) as exc_info:
            raise_if_invalid(nodes, edges, TEST_CATALOG)
        detail = exc_info.value.detail
        assert "error" in detail
        assert detail["error"]["code"] == "WORKFLOW_GRAPH_INVALID"
        assert "details" in detail["error"]
        assert "errors" in detail["error"]["details"]
        assert len(detail["error"]["details"]["errors"]) > 0

    def test_returns_empty_list_when_valid(self):
        nodes = [_node("a", "textInput")]
        edges = []
        result = raise_if_invalid(nodes, edges, TEST_CATALOG)
        assert result == []


# ---------------------------------------------------------------------------
# Tests: build_422_response
# ---------------------------------------------------------------------------

class TestBuild422Response:
    def test_envelope_structure(self):
        errors = [
            GraphValidationError(code="SELF_LOOP", message="Self loop", edge_id="e1"),
            GraphValidationError(code="CYCLE", message="Cycle", edge_id="e2"),
        ]
        response = build_422_response(errors)
        assert response["error"]["code"] == "WORKFLOW_GRAPH_INVALID"
        assert "2 个连接错误" in response["error"]["message"]
        details = response["error"]["details"]["errors"]
        assert len(details) == 2
        assert details[0]["code"] == "SELF_LOOP"
        assert details[0]["edgeId"] == "e1"
        assert details[1]["code"] == "CYCLE"

    def test_includes_node_id_when_present(self):
        errors = [
            GraphValidationError(code="REQUIRED_PORT", message="Missing", node_id="sb", port_id="prompt"),
        ]
        response = build_422_response(errors)
        detail = response["error"]["details"]["errors"][0]
        assert detail["nodeId"] == "sb"
        assert detail["portId"] == "prompt"


# ---------------------------------------------------------------------------
# Tests: get_node_catalog
# ---------------------------------------------------------------------------

class TestGetNodeCatalog:
    def test_catalog_has_expected_kinds(self):
        catalog = get_node_catalog()
        expected_kinds = {"textInput", "storyboard", "textToImage", "imageToVideo", "videoConcat", "output"}
        assert expected_kinds.issubset(set(catalog.keys()))

    def test_catalog_manifests_have_ports(self):
        catalog = get_node_catalog()
        for kind, manifest in catalog.items():
            assert hasattr(manifest, "ports"), f"{kind} missing ports"
            assert hasattr(manifest.ports, "inputs"), f"{kind} missing inputs"
            assert hasattr(manifest.ports, "outputs"), f"{kind} missing outputs"


# ---------------------------------------------------------------------------
# Tests: Multiple errors in one graph
# ---------------------------------------------------------------------------

class TestMultipleErrors:
    def test_self_loop_and_type_mismatch(self):
        nodes = [_node("a", "textInput"), _node("b", "output")]
        edges = [
            _edge("e1", "a", "a", "text", "video"),  # self-loop + type mismatch
            _edge("e2", "a", "b", "text", "video"),   # type mismatch
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        codes = set(e.code for e in errors)
        assert "SELF_LOOP" in codes
        assert "TYPE_MISMATCH" in codes

    def test_multiple_required_ports(self):
        # imageToVideo requires "image" but it's not connected
        nodes = [_node("itv", "imageToVideo")]
        edges = []
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        required_errors = [e for e in errors if e.code == "REQUIRED_PORT"]
        assert len(required_errors) >= 1


# ---------------------------------------------------------------------------
# Tests: UNKNOWN_NODE_KIND
# ---------------------------------------------------------------------------

class TestUnknownNodeKind:
    def test_unknown_node_kind_detected(self):
        nodes = [{"id": "x", "kind": "nope"}]
        errors = validate_graph(nodes, [], TEST_CATALOG)
        codes = [e.code for e in errors]
        assert "UNKNOWN_NODE_KIND" in codes

    def test_unknown_node_kind_message_and_node_id(self):
        nodes = [{"id": "x", "kind": "nope"}]
        errors = validate_graph(nodes, [], TEST_CATALOG)
        unknown = [e for e in errors if e.code == "UNKNOWN_NODE_KIND"][0]
        assert unknown.node_id == "x"
        assert "nope" in unknown.message

    def test_known_kind_not_flagged(self):
        nodes = [_node("a", "textInput")]
        errors = validate_graph(nodes, [], TEST_CATALOG)
        assert not any(e.code == "UNKNOWN_NODE_KIND" for e in errors)

    def test_instance_ports_suppress_unknown_kind(self):
        # A node whose kind is not in the catalog but carries data.ports
        # (module instance) is fully validatable — no UNKNOWN_NODE_KIND.
        nodes = [
            _data_node(
                "m",
                "customKind",
                ports={
                    "inputs": [{"id": "in", "type": "text", "required": True, "cardinality": "one"}],
                    "outputs": [{"id": "out", "type": "text", "required": False, "cardinality": "one"}],
                },
            ),
        ]
        errors = validate_graph(nodes, [], TEST_CATALOG)
        assert not any(e.code == "UNKNOWN_NODE_KIND" for e in errors)


# ---------------------------------------------------------------------------
# Tests: UNKNOWN_HANDLE
# ---------------------------------------------------------------------------

class TestUnknownHandle:
    def test_unknown_source_handle(self):
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "ghost", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        unknown = [e for e in errors if e.code == "UNKNOWN_HANDLE"]
        assert len(unknown) == 1
        assert unknown[0].port_id == "ghost"
        assert unknown[0].node_id == "a"

    def test_unknown_target_handle(self):
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "text", "ghost")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        unknown = [e for e in errors if e.code == "UNKNOWN_HANDLE"]
        assert len(unknown) == 1
        assert unknown[0].port_id == "ghost"
        assert unknown[0].node_id == "b"

    def test_valid_handles_not_flagged(self):
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b", "text", "prompt")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "UNKNOWN_HANDLE" for e in errors)

    def test_missing_handle_not_flagged(self):
        # Omitted handles stay permissive (legacy specs) — no UNKNOWN_HANDLE
        nodes = [_node("a", "textInput"), _node("b", "storyboard")]
        edges = [_edge("e1", "a", "b")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "UNKNOWN_HANDLE" for e in errors)


# ---------------------------------------------------------------------------
# Tests: effective ports (module-aware) — data.ports / module registry / catalog
# ---------------------------------------------------------------------------

_MODULE_INSTANCE_PORTS = {
    "inputs": [
        {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
        {"id": "style", "type": "text", "required": False, "cardinality": "one"},
    ],
    "outputs": [
        {"id": "image", "type": "image", "required": False, "cardinality": "one"},
        {"id": "thumb", "type": "image", "required": False, "cardinality": "one"},
    ],
}


class TestEffectivePorts:
    def test_extension_input_accepts_matching_type(self):
        nodes = [
            _node("t1", "textInput"),
            _data_node("m1", "textToImage", ports=_MODULE_INSTANCE_PORTS,
                       module_id="builtin.seedream.text-to-image"),
        ]
        edges = [_edge("e1", "t1", "m1", "text", "style")]  # text -> text extension
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        structural = [e for e in errors if e.code not in ("REQUIRED_PORT",)]
        assert structural == [], f"Unexpected errors: {[e.code for e in structural]}"

    def test_extension_input_rejects_mismatched_type(self):
        nodes = [
            _node("v1", "videoConcat"),
            _data_node("m1", "textToImage", ports=_MODULE_INSTANCE_PORTS,
                       module_id="builtin.seedream.text-to-image"),
        ]
        edges = [_edge("e1", "v1", "m1", "video", "style")]  # video -> text extension
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert any(e.code == "TYPE_MISMATCH" for e in errors)

    def test_extension_output_accepts_matching_type(self):
        nodes = [
            _data_node("m1", "textToImage", ports=_MODULE_INSTANCE_PORTS,
                       module_id="builtin.seedream.text-to-image"),
            _node("itv", "imageToVideo"),
        ]
        edges = [_edge("e1", "m1", "itv", "thumb", "image")]  # image -> image
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code in ("TYPE_MISMATCH", "UNKNOWN_HANDLE", "DIRECTION") for e in errors)

    def test_unknown_handle_on_module_instance(self):
        nodes = [
            _data_node("m1", "textToImage", ports=_MODULE_INSTANCE_PORTS,
                       module_id="builtin.seedream.text-to-image"),
            _node("itv", "imageToVideo"),
        ]
        edges = [_edge("e1", "m1", "itv", "ghost", "image")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        unknown = [e for e in errors if e.code == "UNKNOWN_HANDLE"]
        assert len(unknown) == 1
        assert unknown[0].port_id == "ghost"

    def test_required_extension_input_flagged_when_unconnected(self):
        nodes = [
            _data_node("m1", "textToImage", ports=_MODULE_INSTANCE_PORTS,
                       module_id="builtin.seedream.text-to-image"),
        ]
        errors = validate_graph(nodes, [], TEST_CATALOG)
        required = [e for e in errors if e.code == "REQUIRED_PORT"]
        # scene is the required input on the instance ports
        assert any(e.port_id == "scene" for e in required)
        # style is optional — not flagged
        assert not any(e.port_id == "style" for e in required)

    def test_core_port_cardinality_override(self):
        # storyboard.prompt is cardinality "one" in the catalog; the instance
        # overrides it to "many", so two edges must be accepted.
        wide = _data_node(
            "sb",
            "storyboard",
            ports={
                "inputs": [{"id": "prompt", "type": "text", "required": True, "cardinality": "many"}],
                "outputs": [{"id": "scenes", "type": "scene", "required": False, "cardinality": "many"}],
            },
        )
        nodes = [_node("t1", "textInput"), _node("t2", "textInput"), wide]
        edges = [
            _edge("e1", "t1", "sb", "text", "prompt"),
            _edge("e2", "t2", "sb", "text", "prompt"),
        ]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code == "CARDINALITY_VIOLATION" for e in errors)

        # Without the override the catalog's "one" rejects the second edge
        nodes_plain = [_node("t1", "textInput"), _node("t2", "textInput"), _node("sb", "storyboard")]
        errors_plain = validate_graph(nodes_plain, edges, TEST_CATALOG)
        assert any(e.code == "CARDINALITY_VIOLATION" for e in errors_plain)

    def test_seedream_module_instance_conclusions(self):
        # Same conclusions as a core textToImage node: a Seedream module
        # instance (builtin.seedream.text-to-image) accepts scene input and
        # rejects unknown handles.
        sd = _data_node("sd", "textToImage",
                        module_id="builtin.seedream.text-to-image",
                        module_version="1.0.0")
        nodes = [_node("sb", "storyboard"), sd, _node("itv", "imageToVideo"), _node("v1", "videoConcat")]
        ok_edges = [_edge("e1", "sb", "sd", "scenes", "scene")]
        errors = validate_graph(nodes, ok_edges, TEST_CATALOG)
        structural = [e for e in errors if e.code not in ("REQUIRED_PORT",)]
        assert structural == [], f"Unexpected errors: {[e.code for e in structural]}"

        bad_edges = [_edge("e1", "sd", "itv", "ghost", "image")]
        errors_bad = validate_graph(nodes, bad_edges, TEST_CATALOG)
        assert any(e.code == "UNKNOWN_HANDLE" for e in errors_bad)

        mismatch_edges = [_edge("e1", "v1", "sd", "video", "scene")]  # video -> scene
        errors_mm = validate_graph(nodes, mismatch_edges, TEST_CATALOG)
        assert any(e.code == "TYPE_MISMATCH" for e in errors_mm)

    def test_module_registry_ports_used_when_no_data_ports(self, monkeypatch):
        # When data.ports is absent, ports resolve via the module registry.
        import backend.app.services.module_registry as registry_module
        from backend.app.schemas.module_definition import ModuleDefinition
        from backend.app.services.module_registry import ModuleRegistry

        mod = ModuleDefinition(
            id="test.custom.extended",
            version="1.0.0",
            status="published",
            baseKind="textToImage",
            category="image",
            label="Extended",
            ports={
                "inputs": [
                    {"id": "scene", "type": "scene", "required": True, "cardinality": "one"},
                    {"id": "style", "type": "text", "required": False, "cardinality": "one"},
                ],
                "outputs": [
                    {"id": "image", "type": "image", "required": False, "cardinality": "one"},
                ],
            },
        )
        registry = ModuleRegistry()
        registry._modules.clear()
        registry._modules[mod.id] = {mod.version: mod}
        monkeypatch.setattr(registry_module, "get_module_registry", lambda: registry)

        nodes = [
            _node("t1", "textInput"),
            _data_node("m1", "textToImage",
                       module_id="test.custom.extended", module_version="1.0.0"),
        ]
        # "style" exists only on the registry module — the catalog has no such port
        edges = [_edge("e1", "t1", "m1", "text", "style")]
        errors = validate_graph(nodes, edges, TEST_CATALOG)
        assert not any(e.code in ("TYPE_MISMATCH", "UNKNOWN_HANDLE", "DIRECTION") for e in errors)

        # A catalog-only port name that the module dropped is now unknown
        edges_bad = [_edge("e1", "t1", "m1", "text", "image")]  # image is an OUTPUT on the module
        errors_bad = validate_graph(nodes, edges_bad, TEST_CATALOG)
        assert any(e.code == "DIRECTION" for e in errors_bad)


# ---------------------------------------------------------------------------
# Tests: catalog contract parity with frontend/src/schemas/node-manifest.ts
# ---------------------------------------------------------------------------

class TestCatalogContractParity:
    """_NODE_CATALOG_V2 must match the FE node-manifest canonical contract."""

    def test_image_to_video_ports(self):
        catalog = get_node_catalog()
        itv = catalog["imageToVideo"]
        by_id = {p.id: p for p in itv.ports.inputs}
        assert "image" in by_id
        assert by_id["image"].required is True
        assert "scene" in by_id
        assert by_id["scene"].required is False
        assert by_id["scene"].cardinality == "one"
        out = itv.ports.outputs[0]
        assert out.id == "video"
        assert out.required is False
        assert out.cardinality == "one"

    def test_outputs_are_never_required(self):
        # "required" is only meaningful for inputs (FE contract)
        catalog = get_node_catalog()
        for kind, manifest in catalog.items():
            for p in manifest.ports.outputs:
                assert p.required is False, f"{kind}.{p.id} must have required=False"

    def test_text_input_and_text_to_image_outputs(self):
        catalog = get_node_catalog()
        assert catalog["textInput"].ports.outputs[0].id == "text"
        assert catalog["textInput"].ports.outputs[0].required is False
        assert catalog["textToImage"].ports.outputs[0].id == "image"
        assert catalog["textToImage"].ports.outputs[0].required is False
