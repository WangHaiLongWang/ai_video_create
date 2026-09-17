"""Tests for Intent Repair."""

import pytest

from backend.app.services.agent_repair import repair_intent, RepairResult
from backend.app.schemas.workflow_intent import (
    WorkflowIntent,
    NodeIntent,
    ConnectionIntent,
    PortRef,
)


class TestValidIntentUnchanged:
    def test_valid_intent_unchanged(self):
        intent = WorkflowIntent(
            name="Valid",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = repair_intent(intent)
        assert result.repaired_intent is not None
        assert len(result.errors) == 0
        assert len(result.repairs) == 0

    def test_valid_pipeline_unchanged(self):
        intent = WorkflowIntent(
            name="Valid Pipeline",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="sb", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.errors) == 0
        assert len(result.repairs) == 0
        assert len(result.repaired_intent.nodes) == 2
        assert len(result.repaired_intent.connections) == 1


class TestRemovesDuplicateConnections:
    def test_removes_duplicate_connections(self):
        intent = WorkflowIntent(
            name="Dup",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 1
        assert any("duplicate" in r.lower() or "Duplicate" in r for r in result.repairs)

    def test_keeps_different_connections(self):
        intent = WorkflowIntent(
            name="Different",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="sb", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 1


class TestRemovesSelfLoops:
    def test_removes_self_loops(self):
        intent = WorkflowIntent(
            name="Loop",
            nodes=[NodeIntent(alias="a", kind="textInput")],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="a", port="text"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 0
        assert any("self-loop" in r.lower() or "self" in r.lower() for r in result.repairs)

    def test_removes_self_loop_preserves_other_connections(self):
        intent = WorkflowIntent(
            name="Mixed",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="a", port="text"),  # self-loop
                ),
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),  # valid
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 1
        assert result.repaired_intent.connections[0].target.node == "b"


class TestRemovesUnknownKind:
    def test_removes_unknown_kind_node(self):
        intent = WorkflowIntent(
            name="Bad Kind",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="nonexistent"),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.nodes) == 1
        assert result.repaired_intent.nodes[0].alias == "a"
        assert any("unknown kind" in r.lower() or "nonexistent" in r for r in result.repairs)

    def test_removes_unknown_kind_and_connections(self):
        intent = WorkflowIntent(
            name="Bad Kind + Conns",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="nonexistent"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="x"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.nodes) == 1
        assert len(result.repaired_intent.connections) == 0


class TestRemovesUnknownPort:
    def test_removes_connection_with_unknown_port(self):
        intent = WorkflowIntent(
            name="Bad Port",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="nonexistent"),
                    target=PortRef(node="b", port="video"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 0
        assert any("unknown port" in r.lower() or "unknown" in r.lower() for r in result.repairs)


class TestRemovesUnknownNodeConnection:
    def test_removes_connection_referencing_unknown_node(self):
        intent = WorkflowIntent(
            name="Ghost Node",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="ghost", port="video"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.connections) == 0
        assert any("unknown node" in r.lower() or "ghost" in r.lower() for r in result.repairs)


class TestTypeMismatchNotRepaired:
    def test_type_mismatch_not_auto_repaired(self):
        intent = WorkflowIntent(
            name="Type Mismatch",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="out", port="video"),
                ),
            ],
        )
        result = repair_intent(intent)
        # Type mismatch is not auto-repaired, so the connection stays
        # but the error remains
        assert len(result.repaired_intent.connections) == 1
        assert len(result.errors) > 0
        codes = [e.get("code") for e in result.errors]
        assert "TYPE_MISMATCH" in codes


class TestMaxRepairsLimit:
    def test_max_repairs_limit(self):
        # Create an intent with many issues
        intent = WorkflowIntent(
            name="Broken",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="nonexistent"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="x"),
                ),
            ],
        )
        result = repair_intent(intent, max_repairs=2)
        assert result.attempts <= 2

    def test_single_repair_round(self):
        intent = WorkflowIntent(
            name="One Round",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="nonexistent"),
            ],
        )
        result = repair_intent(intent, max_repairs=1)
        assert result.attempts == 1


class TestDuplicateAliasRepair:
    def test_renames_duplicate_aliases(self):
        intent = WorkflowIntent(
            name="Dup Alias",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="a", kind="output"),
            ],
        )
        result = repair_intent(intent)
        aliases = [n.alias for n in result.repaired_intent.nodes]
        assert len(aliases) == 2
        assert aliases[0] == "a"
        assert aliases[1] == "a_2"  # renamed
        assert len(result.errors) == 0

    def test_multiple_duplicate_aliases(self):
        intent = WorkflowIntent(
            name="Multi Dup",
            nodes=[
                NodeIntent(alias="x", kind="textInput"),
                NodeIntent(alias="x", kind="storyboard"),
                NodeIntent(alias="x", kind="output"),
            ],
        )
        result = repair_intent(intent)
        aliases = [n.alias for n in result.repaired_intent.nodes]
        assert aliases[0] == "x"
        assert aliases[1] == "x_2"
        assert aliases[2] == "x_3"


class TestRepairPreservesOriginal:
    def test_repair_does_not_mutate_original(self):
        original_connections = [
            ConnectionIntent(
                source=PortRef(node="a", port="text"),
                target=PortRef(node="a", port="text"),
            ),
        ]
        intent = WorkflowIntent(
            name="Original",
            nodes=[NodeIntent(alias="a", kind="textInput")],
            connections=original_connections,
        )
        result = repair_intent(intent)
        # Original intent should be unchanged
        assert len(intent.connections) == 1
        # Repaired intent should have the connection removed
        assert len(result.repaired_intent.connections) == 0


class TestRepairResult:
    def test_repair_result_structure(self):
        intent = WorkflowIntent(
            name="Test",
            nodes=[NodeIntent(alias="in", kind="textInput")],
        )
        result = repair_intent(intent)
        assert isinstance(result, RepairResult)
        assert isinstance(result.repaired_intent, WorkflowIntent)
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.repairs, list)
        assert isinstance(result.attempts, int)


class TestCombinedRepairs:
    def test_fixes_multiple_issues(self):
        """Intent with duplicate connections, self-loop, and unknown kind."""
        intent = WorkflowIntent(
            name="Messy",
            nodes=[
                NodeIntent(alias="a", kind="textInput"),
                NodeIntent(alias="b", kind="storyboard"),
                NodeIntent(alias="c", kind="fakeNode"),
            ],
            connections=[
                # Duplicate connection
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="b", port="prompt"),
                ),
                # Self-loop
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="a", port="text"),
                ),
            ],
        )
        result = repair_intent(intent)
        assert len(result.repaired_intent.nodes) == 2  # fakeNode removed
        assert len(result.repaired_intent.connections) == 1  # dup + self-loop removed
        assert len(result.repairs) > 0

    def test_valid_intent_no_repairs_needed(self):
        """A fully valid intent goes through without any repairs."""
        from backend.app.services.agent_tools import validate_intent

        intent = WorkflowIntent(
            name="Full Pipeline",
            nodes=[
                NodeIntent(alias="in", kind="textInput"),
                NodeIntent(alias="sb", kind="storyboard"),
                NodeIntent(alias="img", kind="textToImage"),
                NodeIntent(alias="vid", kind="imageToVideo"),
                NodeIntent(alias="concat", kind="videoConcat"),
                NodeIntent(alias="out", kind="output"),
            ],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="in", port="text"),
                    target=PortRef(node="sb", port="prompt"),
                ),
                ConnectionIntent(
                    source=PortRef(node="sb", port="scenes"),
                    target=PortRef(node="img", port="scene"),
                    mode="map",
                ),
                ConnectionIntent(
                    source=PortRef(node="img", port="images"),
                    target=PortRef(node="vid", port="image"),
                    mode="map",
                ),
                ConnectionIntent(
                    source=PortRef(node="vid", port="videos"),
                    target=PortRef(node="concat", port="videos"),
                    mode="aggregate",
                ),
                ConnectionIntent(
                    source=PortRef(node="concat", port="video"),
                    target=PortRef(node="out", port="video"),
                ),
            ],
        )
        # Verify it's actually valid first
        validation = validate_intent(intent)
        assert validation.success

        result = repair_intent(intent)
        assert len(result.errors) == 0
        assert len(result.repairs) == 0
        assert len(result.repaired_intent.nodes) == 6
        assert len(result.repaired_intent.connections) == 5
