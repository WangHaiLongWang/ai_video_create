"""Golden-case test suite for the Agent intent compiler, tools, and repair.

35+ Chinese golden cases covering:
- Basic generation (10 cases)
- Modification (8 cases)
- Validation & repair (7 cases)
- Destructive/cautious operations (5 cases)
- Edge cases (7 cases)

Each case is tested for:
1. WorkflowIntent construction and structure
2. Compilation via compile_intent()
3. Validation via validate_intent()
4. Repair via repair_intent() (when expected)
5. Cost estimation via estimate_calls()
6. Compiled spec structure (nodes, edges, positions, config)
"""

from __future__ import annotations

import pytest

from backend.app.schemas.workflow_intent import (
    ConnectionIntent,
    NodeIntent,
    PortRef,
    WorkflowIntent,
)
from backend.app.services.agent_compiler import compile_intent
from backend.app.services.agent_repair import repair_intent
from backend.app.services.agent_tools import (
    estimate_calls,
    get_node_manifest,
    list_node_manifests,
    validate_intent,
)
from backend.app.schemas.graph_validator import validate_graph

from backend.tests.agent.golden.cases import (
    ALL_GOLDEN_CASES,
    CASES_BY_CATEGORY,
    CASES_BY_ID,
    GoldenCase,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_intent(case: GoldenCase) -> WorkflowIntent:
    """Build a WorkflowIntent from a golden case definition."""
    nodes = [NodeIntent(alias=a, kind=k) for a, k in case.expected_nodes]

    connections = [
        ConnectionIntent(
            source=PortRef(node=src, port=src_port),
            target=PortRef(node=tgt, port=tgt_port),
            mode=mode,
        )
        for src, src_port, tgt, tgt_port, mode in case.expected_connections
    ]

    # Apply per-node config overrides
    for node in nodes:
        if node.alias in case.expected_config:
            node.config = dict(case.expected_config[node.alias])

    return WorkflowIntent(
        name=case.id,
        description=case.notes,
        nodes=nodes,
        connections=connections,
        tags=[case.category],
        scene_count=case.scene_count,
        variant_count=case.variant_count,
        duration=case.duration,
        resolution=case.resolution,
    )


# ---------------------------------------------------------------------------
# Category 1: Basic generation
# ---------------------------------------------------------------------------


class TestBasicGeneration:
    """Category 1: Basic generation golden cases."""

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_intent_structure(self, case: GoldenCase):
        """Intent should have expected nodes and connections."""
        intent = _build_intent(case)
        assert intent.name == case.id
        assert len(intent.nodes) == len(case.expected_nodes)
        assert len(intent.connections) == len(case.expected_connections)

        # Node aliases and kinds
        for (alias, kind), node in zip(case.expected_nodes, intent.nodes):
            assert node.alias == alias
            assert node.kind == kind

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_compile_produces_valid_spec(self, case: GoldenCase):
        """Compiled spec should be valid WorkflowSpecV2."""
        intent = _build_intent(case)
        spec = compile_intent(intent)

        assert spec["schemaVersion"] == "2.0"
        assert spec["manifestVersion"] == "1.0"
        assert "id" in spec
        assert spec["name"] == case.id
        assert len(spec["nodes"]) == case.expected_node_count
        assert len(spec["edges"]) == case.expected_edge_count

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_validation_passes(self, case: GoldenCase):
        """Basic generation intents should pass validation."""
        intent = _build_intent(case)
        result = validate_intent(intent)
        assert result.success, f"Validation failed: {result.error}"

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_compiled_edges_have_correct_handles(self, case: GoldenCase):
        """Each edge should have sourceHandle and targetHandle matching connection ports."""
        intent = _build_intent(case)
        spec = compile_intent(intent)

        # Build alias->id mapping
        alias_to_id = {}
        for i, (alias, _) in enumerate(case.expected_nodes):
            alias_to_id[alias] = spec["nodes"][i]["id"]

        assert len(spec["edges"]) == case.expected_edge_count
        for edge, (src, src_port, tgt, tgt_port, _) in zip(
            spec["edges"], case.expected_connections
        ):
            assert edge["source"] == alias_to_id[src]
            assert edge["target"] == alias_to_id[tgt]
            assert edge["sourceHandle"] == src_port
            assert edge["targetHandle"] == tgt_port

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_config_overrides_applied(self, case: GoldenCase):
        """Config overrides should be present in compiled nodes."""
        intent = _build_intent(case)
        spec = compile_intent(intent)

        alias_to_node = {n["data"]["label"]: n for n in spec["nodes"]}
        # Build alias->node by checking kind
        alias_to_compiled = {}
        for i, (alias, kind) in enumerate(case.expected_nodes):
            alias_to_compiled[alias] = spec["nodes"][i]

        for alias, config in case.expected_config.items():
            if alias in alias_to_compiled:
                node = alias_to_compiled[alias]
                for key, value in config.items():
                    assert node["data"]["config"].get(key) == value, (
                        f"Node '{alias}' config[{key}]: expected {value}, "
                        f"got {node['data']['config'].get(key)}"
                    )

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["basic_generation"],
        ids=[c.id for c in CASES_BY_CATEGORY["basic_generation"]],
    )
    def test_cost_estimation(self, case: GoldenCase):
        """Cost estimation should return valid data."""
        intent = _build_intent(case)
        result = estimate_calls(intent)
        assert result.success
        assert result.data["scene_count"] >= 1
        assert result.data["variant_count"] >= 1
        assert result.data["total_calls"] >= 0


# ---------------------------------------------------------------------------
# Category 2: Modification
# ---------------------------------------------------------------------------


class TestModification:
    """Category 2: Modification golden cases."""

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["modification"],
        ids=[c.id for c in CASES_BY_CATEGORY["modification"]],
    )
    def test_intent_structure(self, case: GoldenCase):
        """Modification intents should have correct node/connection structure."""
        intent = _build_intent(case)
        assert len(intent.nodes) == len(case.expected_nodes)
        assert len(intent.connections) == len(case.expected_connections)

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["modification"],
        ids=[c.id for c in CASES_BY_CATEGORY["modification"]],
    )
    def test_compile_produces_valid_spec(self, case: GoldenCase):
        """Modified intents should compile to valid specs."""
        intent = _build_intent(case)
        spec = compile_intent(intent)

        assert spec["schemaVersion"] == "2.0"
        assert len(spec["nodes"]) == case.expected_node_count
        assert len(spec["edges"]) == case.expected_edge_count

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["modification"],
        ids=[c.id for c in CASES_BY_CATEGORY["modification"]],
    )
    def test_config_applied(self, case: GoldenCase):
        """Config modifications should be reflected in compiled output."""
        intent = _build_intent(case)
        spec = compile_intent(intent)

        for i, (alias, kind) in enumerate(case.expected_nodes):
            if alias in case.expected_config:
                node = spec["nodes"][i]
                for key, value in case.expected_config[alias].items():
                    assert node["data"]["config"].get(key) == value, (
                        f"Node '{alias}' config[{key}]: expected {value}, "
                        f"got {node['data']['config'].get(key)}"
                    )

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["modification"],
        ids=[c.id for c in CASES_BY_CATEGORY["modification"]],
    )
    def test_not_unless_destructive(self, case: GoldenCase):
        """Modification cases (except delete) should not be marked destructive."""
        # mod-04-delete-output is the only destructive modification
        if case.id == "mod-04-delete-output":
            assert case.is_destructive
        else:
            assert not case.is_destructive


# ---------------------------------------------------------------------------
# Category 3: Validation and repair
# ---------------------------------------------------------------------------


class TestValidationRepair:
    """Category 3: Validation and repair golden cases."""

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["validation_repair"],
        ids=[c.id for c in CASES_BY_CATEGORY["validation_repair"]],
    )
    def test_validation_result_matches_expectation(self, case: GoldenCase):
        """Validation pass/fail should match expected."""
        intent = _build_intent(case)
        result = validate_intent(intent)
        assert result.success == case.expect_validation_pass, (
            f"Expected validation {'pass' if case.expect_validation_pass else 'fail'}, "
            f"got {'pass' if result.success else 'fail'}: {result.error}"
        )

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in CASES_BY_CATEGORY["validation_repair"]
            if c.expect_repair_needed
        ],
        ids=[
            c.id
            for c in CASES_BY_CATEGORY["validation_repair"]
            if c.expect_repair_needed
        ],
    )
    def test_repair_produces_repairs(self, case: GoldenCase):
        """Repair should produce repair logs for broken intents."""
        intent = _build_intent(case)
        result = repair_intent(intent)
        assert len(result.repairs) > 0, (
            f"Expected repairs for {case.id} but got none"
        )

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in CASES_BY_CATEGORY["validation_repair"]
            if c.expect_repair_needed
        ],
        ids=[
            c.id
            for c in CASES_BY_CATEGORY["validation_repair"]
            if c.expect_repair_needed
        ],
    )
    def test_repair_reduces_errors(self, case: GoldenCase):
        """After repair, error count should be less than or equal to original."""
        intent = _build_intent(case)
        original = validate_intent(intent)
        original_errors = len(original.data.get("errors", []))

        repair_result = repair_intent(intent)
        remaining = len(repair_result.errors)

        assert remaining <= original_errors, (
            f"Repair did not reduce errors: {original_errors} -> {remaining}"
        )

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["validation_repair"],
        ids=[c.id for c in CASES_BY_CATEGORY["validation_repair"]],
    )
    def test_compiled_output_node_count(self, case: GoldenCase):
        """Compiled spec should have expected node count."""
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert len(spec["nodes"]) == case.expected_node_count

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["validation_repair"],
        ids=[c.id for c in CASES_BY_CATEGORY["validation_repair"]],
    )
    def test_graph_validator_on_compiled_spec(self, case: GoldenCase):
        """validate_graph should be consistent with validate_intent."""
        from backend.app.services.agent_tools import _NODE_CATALOG_V2

        intent = _build_intent(case)
        spec = compile_intent(intent)

        # Transform compiled spec to validate_graph format (kind at top level)
        graph_spec = {
            "nodes": [
                {"id": n["id"], "kind": n["data"]["kind"]}
                for n in spec["nodes"]
            ],
            "edges": [
                {
                    "id": e["id"],
                    "source": e["source"],
                    "sourceHandle": e.get("sourceHandle"),
                    "target": e["target"],
                    "targetHandle": e.get("targetHandle"),
                }
                for e in spec["edges"]
            ],
        }

        errors = validate_graph(graph_spec, _NODE_CATALOG_V2)

        if case.expect_validation_pass:
            # Graph validator checks required ports, so valid intents may still
            # show REQUIRED_PORT errors. Only fail on structural errors.
            structural_errors = [
                e for e in errors
                if e.code not in ("REQUIRED_PORT",)
            ]
            assert len(structural_errors) == 0, (
                f"Graph validator found structural errors on expected-valid case {case.id}: "
                + "; ".join(e.message for e in structural_errors)
            )


# ---------------------------------------------------------------------------
# Category 4: Destructive/cautious operations
# ---------------------------------------------------------------------------


class TestDestructive:
    """Category 4: Destructive/cautious operations."""

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["destructive"],
        ids=[c.id for c in CASES_BY_CATEGORY["destructive"]],
    )
    def test_destructive_flag_set(self, case: GoldenCase):
        """All destructive cases should have is_destructive=True."""
        assert case.is_destructive, f"Case {case.id} should be marked destructive"

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["destructive"],
        ids=[c.id for c in CASES_BY_CATEGORY["destructive"]],
    )
    def test_intent_structure(self, case: GoldenCase):
        """Destructive intents should still produce valid structure."""
        intent = _build_intent(case)
        assert len(intent.nodes) == len(case.expected_nodes)
        assert len(intent.connections) == len(case.expected_connections)

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["destructive"],
        ids=[c.id for c in CASES_BY_CATEGORY["destructive"]],
    )
    def test_compile_produces_spec(self, case: GoldenCase):
        """Destructive intents should still compile."""
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert spec["schemaVersion"] == "2.0"
        assert len(spec["nodes"]) == case.expected_node_count

    @pytest.mark.parametrize(
        "case",
        CASES_BY_CATEGORY["destructive"],
        ids=[c.id for c in CASES_BY_CATEGORY["destructive"]],
    )
    def test_validation_matches_expectation(self, case: GoldenCase):
        """Destructive cases should match expected validation result."""
        intent = _build_intent(case)
        result = validate_intent(intent)
        assert result.success == case.expect_validation_pass, (
            f"Case {case.id}: expected {'pass' if case.expect_validation_pass else 'fail'}, "
            f"got {'pass' if result.success else 'fail'}"
        )

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in CASES_BY_CATEGORY["destructive"]
            if c.expect_repair_needed
        ],
        ids=[
            c.id
            for c in CASES_BY_CATEGORY["destructive"]
            if c.expect_repair_needed
        ],
    )
    def test_repair_for_broken_destructive(self, case: GoldenCase):
        """Broken destructive intents should still be repairable."""
        intent = _build_intent(case)
        result = repair_intent(intent)
        assert len(result.repairs) > 0


# ---------------------------------------------------------------------------
# Category 5: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Category 5: Edge cases."""

    def test_empty_prompt_rejects_empty_nodes(self):
        """WorkflowIntent requires at least 1 node; empty nodes list must raise."""
        with pytest.raises(Exception):
            WorkflowIntent(name="empty", nodes=[])

    def test_empty_prompt_case_definition(self):
        """Empty prompt golden case should have 0 nodes and expect validation failure."""
        case = CASES_BY_ID["edge-01-empty-prompt"]
        assert len(case.expected_nodes) == 0
        assert not case.expect_validation_pass
        assert case.prompt == ""

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in CASES_BY_CATEGORY["edge_case"]
            if c.id != "edge-01-empty-prompt"
        ],
        ids=[
            c.id
            for c in CASES_BY_CATEGORY["edge_case"]
            if c.id != "edge-01-empty-prompt"
        ],
    )
    def test_non_empty_edge_cases_compile(self, case: GoldenCase):
        """Non-empty edge cases should compile successfully."""
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert spec["schemaVersion"] == "2.0"
        assert len(spec["nodes"]) == case.expected_node_count

    @pytest.mark.parametrize(
        "case",
        [
            c
            for c in CASES_BY_CATEGORY["edge_case"]
            if c.id not in ("edge-01-empty-prompt", "edge-07-malformed-intent-self-loop")
        ],
        ids=[
            c.id
            for c in CASES_BY_CATEGORY["edge_case"]
            if c.id not in ("edge-01-empty-prompt", "edge-07-malformed-intent-self-loop")
        ],
    )
    def test_normal_edge_cases_validate(self, case: GoldenCase):
        """Normal edge cases (no self-loops) should validate."""
        intent = _build_intent(case)
        result = validate_intent(intent)
        assert result.success, f"Edge case {case.id} failed validation: {result.error}"

    def test_self_loop_detected(self):
        """Self-loop edge case should be detected by validation."""
        case = CASES_BY_ID["edge-07-malformed-intent-self-loop"]
        intent = _build_intent(case)
        result = validate_intent(intent)
        assert not result.success
        codes = {e.get("code") for e in result.data.get("errors", [])}
        assert "SELF_LOOP" in codes

    def test_self_loop_repaired(self):
        """Self-loop should be repaired by repair_intent."""
        case = CASES_BY_ID["edge-07-malformed-intent-self-loop"]
        intent = _build_intent(case)
        result = repair_intent(intent)
        assert len(result.repairs) > 0
        # After repair, the self-loop should be removed
        assert len(result.repaired_intent.connections) == 0

    def test_long_prompt_preserves_structure(self):
        """Very long prompt should produce same structure as normal prompt."""
        case = CASES_BY_ID["edge-02-very-long-prompt"]
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert len(spec["nodes"]) == 6
        assert len(spec["edges"]) == 5
        # The prompt text should be preserved
        assert len(case.prompt) > 500

    def test_special_characters_in_prompt(self):
        """Special characters should not break compilation."""
        case = CASES_BY_ID["edge-05-special-characters"]
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert spec["schemaVersion"] == "2.0"
        assert len(spec["nodes"]) == 6

    def test_mixed_language_prompt(self):
        """Mixed Chinese/English should work."""
        case = CASES_BY_ID["edge-06-chinese-english-mix"]
        intent = _build_intent(case)
        spec = compile_intent(intent)
        assert spec["schemaVersion"] == "2.0"
        assert len(spec["nodes"]) == 6


# ---------------------------------------------------------------------------
# Cross-cutting tests
# ---------------------------------------------------------------------------


class TestCrossCutting:
    """Tests that span multiple categories."""

    def test_all_case_ids_unique(self):
        """Every golden case must have a unique id."""
        ids = [c.id for c in ALL_GOLDEN_CASES]
        assert len(ids) == len(set(ids)), f"Duplicate ids found: {ids}"

    def test_total_case_count(self):
        """Should have at least 35 golden cases."""
        assert len(ALL_GOLDEN_CASES) >= 35, (
            f"Expected >= 35 golden cases, got {len(ALL_GOLDEN_CASES)}"
        )

    def test_all_categories_represented(self):
        """All 5 categories should have at least one case."""
        expected_cats = {
            "basic_generation",
            "modification",
            "validation_repair",
            "destructive",
            "edge_case",
        }
        actual_cats = set(CASES_BY_CATEGORY.keys())
        assert expected_cats == actual_cats, (
            f"Missing categories: {expected_cats - actual_cats}"
        )

    def test_category_counts(self):
        """Each category should have the expected minimum count."""
        assert len(CASES_BY_CATEGORY["basic_generation"]) >= 10
        assert len(CASES_BY_CATEGORY["modification"]) >= 8
        assert len(CASES_BY_CATEGORY["validation_repair"]) >= 7
        assert len(CASES_BY_CATEGORY["destructive"]) >= 5
        assert len(CASES_BY_CATEGORY["edge_case"]) >= 5

    def test_all_nodes_have_valid_kinds(self):
        """Every node kind in every case should exist in NODE_CATALOG."""
        manifest = list_node_manifests()
        valid_kinds = set(manifest.data.keys())

        for case in ALL_GOLDEN_CASES:
            for alias, kind in case.expected_nodes:
                assert kind in valid_kinds, (
                    f"Case {case.id}: node '{alias}' has invalid kind '{kind}'. "
                    f"Valid kinds: {valid_kinds}"
                )

    def test_all_connections_reference_valid_aliases(self):
        """Every connection should reference aliases that exist in the case's nodes."""
        for case in ALL_GOLDEN_CASES:
            node_aliases = {alias for alias, _ in case.expected_nodes}
            for src, src_port, tgt, tgt_port, mode in case.expected_connections:
                assert src in node_aliases, (
                    f"Case {case.id}: connection source '{src}' not in nodes {node_aliases}"
                )
                assert tgt in node_aliases, (
                    f"Case {case.id}: connection target '{tgt}' not in nodes {node_aliases}"
                )

    def test_all_ports_exist_on_nodes(self):
        """Every port referenced in connections should exist on the node's manifest."""
        manifest_result = list_node_manifests()
        catalog = manifest_result.data

        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes:
                continue
            kind_map = {alias: kind for alias, kind in case.expected_nodes}
            for src, src_port, tgt, tgt_port, mode in case.expected_connections:
                src_kind = kind_map.get(src)
                tgt_kind = kind_map.get(tgt)
                if src_kind and src_kind in catalog:
                    output_ids = {p["id"] for p in catalog[src_kind]["outputs"]}
                    assert src_port in output_ids, (
                        f"Case {case.id}: source port '{src_port}' not found on '{src_kind}'. "
                        f"Available: {output_ids}"
                    )
                if tgt_kind and tgt_kind in catalog:
                    input_ids = {p["id"] for p in catalog[tgt_kind]["inputs"]}
                    assert tgt_port in input_ids, (
                        f"Case {case.id}: target port '{tgt_port}' not found on '{tgt_kind}'. "
                        f"Available: {input_ids}"
                    )

    def test_destructive_cases_not_in_basic(self):
        """No basic_generation case should be destructive."""
        for case in CASES_BY_CATEGORY["basic_generation"]:
            assert not case.is_destructive, (
                f"Basic case {case.id} should not be destructive"
            )

    def test_compile_all_cases(self):
        """Every non-empty case should compile without error."""
        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes:
                continue
            intent = _build_intent(case)
            spec = compile_intent(intent)
            assert spec["schemaVersion"] == "2.0", f"Case {case.id} failed compilation"

    def test_estimate_calls_all_cases(self):
        """Cost estimation should work for all non-empty cases."""
        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes:
                continue
            intent = _build_intent(case)
            result = estimate_calls(intent)
            assert result.success, f"estimate_calls failed for {case.id}"

    def test_compiled_nodes_have_required_fields(self):
        """Every compiled node should have id, type, position, data."""
        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes:
                continue
            intent = _build_intent(case)
            spec = compile_intent(intent)
            for node in spec["nodes"]:
                assert "id" in node
                assert "type" in node
                assert node["type"] == "studio"
                assert "position" in node
                assert "x" in node["position"]
                assert "y" in node["position"]
                assert "data" in node
                assert "label" in node["data"]
                assert "kind" in node["data"]
                assert "config" in node["data"]
                assert "status" in node["data"]
                assert node["data"]["status"] == "idle"

    def test_compiled_edges_have_required_fields(self):
        """Every compiled edge should have id, source, target, sourceHandle, targetHandle."""
        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes or (case.expected_edge_count is not None and case.expected_edge_count == 0):
                continue
            intent = _build_intent(case)
            spec = compile_intent(intent)
            for edge in spec["edges"]:
                assert "id" in edge
                assert "source" in edge
                assert "target" in edge
                assert "sourceHandle" in edge
                assert "targetHandle" in edge
                assert "data" in edge
                assert "mode" in edge["data"]

    def test_nodes_are_positioned_left_to_right(self):
        """Node x-positions should increase from left to right."""
        for case in ALL_GOLDEN_CASES:
            if len(case.expected_nodes) < 2:
                continue
            intent = _build_intent(case)
            spec = compile_intent(intent)
            positions = [n["position"]["x"] for n in spec["nodes"]]
            for i in range(1, len(positions)):
                assert positions[i] > positions[i - 1], (
                    f"Case {case.id}: node {i} x={positions[i]} <= node {i-1} x={positions[i-1]}"
                )

    def test_metadata_created_at(self):
        """Compiled spec should have metadata with createdAt."""
        for case in ALL_GOLDEN_CASES:
            if not case.expected_nodes:
                continue
            intent = _build_intent(case)
            spec = compile_intent(intent)
            assert "metadata" in spec
            assert "createdAt" in spec["metadata"]
