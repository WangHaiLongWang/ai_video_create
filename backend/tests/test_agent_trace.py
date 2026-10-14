"""Tests for Agent Trace (HARD-403 trace + audit half).

Covers:
1. generate writes exactly one trace with steps (kind/prompt_hash shape)
2. the raw prompt is absent from every persisted row
3. a seeded secret in a step detail is masked on read-back
4. modify/apply writes a trace AND an audit_logger line
5. repair_count increments per repair pass
6. list_traces filters (workflow_id/kind), limit/offset, unfiltered total
7. get_trace 404s on unknown id
8. trace write failure does not break the agent operation
9. both v1 and v2 paths produce traces
"""

from __future__ import annotations

import hashlib
import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.app.db.connection import close_connection, get_connection, init_db
from backend.app.main import app
from backend.app.providers import clear_providers, init_providers
from backend.app.services import agent_trace
from backend.app.services.agent_trace import (
    AgentTraceContext,
    compute_prompt_hash,
    get_trace,
    list_traces,
    start_trace,
)
from backend.app.services.audit_logger import AuditLogger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test runs against an isolated database."""
    monkeypatch.setattr("backend.app.db.connection._DB_PATH", tmp_path / "test.db")
    close_connection()
    init_db()
    yield
    close_connection()


@pytest.fixture()
def client():
    # Pin mock-only providers AFTER lifespan startup so the app's real-LLM
    # registration (env keys) cannot leak into these hermetic tests.
    with TestClient(app) as c:
        clear_providers()
        init_providers(mock=True)
        yield c
    clear_providers()


@pytest.fixture()
def audit_file(tmp_path, monkeypatch):
    """Redirect the audit_logger singleton to a temp logs/audit.jsonl."""
    log_path = tmp_path / "logs" / "audit.jsonl"
    fresh = AuditLogger(log_path=log_path)
    monkeypatch.setattr(
        "backend.app.services.audit_logger.audit_logger", fresh
    )
    return log_path


def _dump_all_rows() -> str:
    """Serialize both trace tables to a single string for substring checks."""
    conn = get_connection()
    chunks: list[str] = []
    for table in ("agent_traces", "agent_trace_steps"):
        for row in conn.execute(f"SELECT * FROM {table}").fetchall():
            chunks.append(str(tuple(row)))
    return "\n".join(chunks)


def _read_audit_lines(audit_file):
    if not audit_file.exists():
        return []
    return [
        json.loads(line)
        for line in audit_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 1. generate writes exactly one trace with steps
# ---------------------------------------------------------------------------

class TestGenerateWritesTrace:
    def test_generate_writes_exactly_one_trace(self, client):
        prompt = "生成一个滑雪教学视频，共 3 个镜头"
        resp = client.post("/api/agent/generate", json={"prompt": prompt})
        assert resp.status_code == 200
        assert resp.json()["nodes"], "generate must still return a spec"

        conn = get_connection()
        rows = conn.execute("SELECT * FROM agent_traces").fetchall()
        assert len(rows) == 1, "exactly one trace per generate"
        row = dict(rows[0])
        assert row["kind"] == "generate"
        assert row["status"] in ("ok", "error")

        # prompt_hash is a 64-char lowercase hex SHA-256 of the prompt
        assert re.fullmatch(r"[0-9a-f]{64}", row["prompt_hash"])
        assert row["prompt_hash"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        detail = get_trace(row["trace_id"])
        assert detail is not None
        assert len(detail["steps"]) >= 1, "generate trace must carry steps"

        allowed = set(agent_trace.STEP_KINDS)
        for step in detail["steps"]:
            assert step["kind"] in allowed
            assert step["status"] in ("ok", "error", "skipped")
            assert isinstance(step["detail"], dict)

    def test_generate_summary_step_count_matches_steps(self, client):
        client.post("/api/agent/generate", json={"prompt": "step count check"})
        listing = list_traces(kind="generate")
        assert listing["total"] == 1
        summary = listing["traces"][0]
        detail = get_trace(summary["trace_id"])
        assert summary["step_count"] == len(detail["steps"])
        assert summary["prompt_hash"] == compute_prompt_hash("step count check")


# ---------------------------------------------------------------------------
# 2. raw prompt never persisted
# ---------------------------------------------------------------------------

class TestPromptNeverPersisted:
    def test_raw_prompt_absent_from_all_rows(self, client):
        prompt = "RAW_PROMPT_MARKER_XYZ_12345 一个非常独特的提示词"
        resp = client.post("/api/agent/generate", json={"prompt": prompt})
        assert resp.status_code == 200

        dump = _dump_all_rows()
        assert dump, "trace rows must exist"
        assert prompt not in dump
        assert "RAW_PROMPT_MARKER_XYZ_12345" not in dump

    def test_modify_instruction_absent_from_all_rows(self, client):
        gen = client.post("/api/agent/generate", json={"prompt": "基础工作流"})
        workflow_id = gen.json()["id"]
        instruction = "INSTRUCTION_MARKER_QQQ_999 请删除最后一个节点"
        resp = client.post(
            "/api/agent/modify",
            json={"workflow_id": workflow_id, "instruction": instruction},
        )
        assert resp.status_code == 200

        dump = _dump_all_rows()
        assert "INSTRUCTION_MARKER_QQQ_999" not in dump


# ---------------------------------------------------------------------------
# 3. seeded secret masked on read-back
# ---------------------------------------------------------------------------

class TestSecretsMasked:
    def test_seeded_secret_masked_on_readback(self, client):
        secret = "sk-" + "a1b2c3d4e5f6g7h8i9j0"  # sk- + 20 chars
        assert len(secret) == 23

        ctx = start_trace("generate", workflow_id=None, prompt="mask me")
        assert isinstance(ctx, AgentTraceContext)
        ctx.add_step(
            "tool",
            "seeded_secret",
            "ok",
            0,
            {"api_key": secret, "nested": {"token": secret}, "note": "harmless"},
        )
        ctx.finish(status="ok")

        detail = get_trace(ctx.trace_id)
        assert detail is not None
        step = next(s for s in detail["steps"] if s["name"] == "seeded_secret")
        flat = json.dumps(step["detail"], ensure_ascii=False)
        assert secret not in flat
        assert secret not in json.dumps(detail, ensure_ascii=False)
        # masking keeps a visible, redacted form rather than dropping the field
        assert step["detail"]["api_key"] != secret
        assert step["detail"]["nested"]["token"] != secret
        assert step["detail"]["note"] == "harmless"

        dump = _dump_all_rows()
        assert secret not in dump

    def test_secret_in_module_diff_summary_masked(self, client):
        secret = "sk-" + "z9y8x7w6v5u4t3s2r1q0"
        ctx = start_trace("modify", workflow_id="wf-1", prompt="p")
        ctx.finish(
            status="ok",
            module_diff_summary={
                "added": 1,
                "removed": 0,
                "updated": 0,
                "modules": [{"module_id": secret}],
            },
        )
        detail = get_trace(ctx.trace_id)
        assert secret not in json.dumps(detail, ensure_ascii=False)
        assert secret not in _dump_all_rows()


# ---------------------------------------------------------------------------
# 4. modify / apply write a trace and an audit_logger line
# ---------------------------------------------------------------------------

class TestModifyApplyAudit:
    def test_modify_writes_trace_and_audit_line(self, client, audit_file):
        gen = client.post("/api/agent/generate", json={"prompt": "审计 modify 测试"})
        workflow_id = gen.json()["id"]

        instruction = "添加一个输出节点"
        resp = client.post(
            "/api/agent/modify",
            json={"workflow_id": workflow_id, "instruction": instruction},
        )
        assert resp.status_code == 200

        traces = list_traces(kind="modify")
        assert traces["total"] == 1
        summary = traces["traces"][0]
        assert summary["workflow_id"] == workflow_id
        assert summary["prompt_hash"] == hashlib.sha256(instruction.encode("utf-8")).hexdigest()

        lines = _read_audit_lines(audit_file)
        modify_events = [e for e in lines if e["event_type"] == "agent.modify"]
        assert len(modify_events) == 1
        event = modify_events[0]
        assert event["detail"]["prompt_hash"] == summary["prompt_hash"]
        assert "repair_count" in event["detail"]
        assert "module_diff_summary" in event["detail"]
        assert instruction not in json.dumps(event, ensure_ascii=False)

    def test_apply_writes_trace_and_audit_line(self, client, audit_file):
        gen = client.post("/api/agent/generate", json={"prompt": "审计 apply 测试"})
        workflow_id = gen.json()["id"]

        resp = client.post(
            "/api/agent/apply-patch",
            json={
                "workflow_id": workflow_id,
                "patch": {
                    "description": "空 patch 审计测试",
                    "add_nodes": [],
                    "remove_nodes": [],
                    "update_nodes": [],
                    "add_edges": [],
                    "remove_edges": [],
                },
            },
        )
        assert resp.status_code == 200

        traces = list_traces(kind="apply")
        assert traces["total"] == 1
        summary = traces["traces"][0]
        assert summary["workflow_id"] == workflow_id

        detail = get_trace(summary["trace_id"])
        assert detail["module_diff_summary"] is not None
        assert detail["module_diff_summary"]["added"] == 0

        lines = _read_audit_lines(audit_file)
        apply_events = [e for e in lines if e["event_type"] == "agent.apply"]
        assert len(apply_events) == 1
        assert apply_events[0]["detail"]["prompt_hash"] == summary["prompt_hash"]

    def test_audit_line_written_to_logs_audit_jsonl(self, client, audit_file):
        gen = client.post("/api/agent/generate", json={"prompt": "audit 文件路径"})
        workflow_id = gen.json()["id"]
        client.post(
            "/api/agent/modify",
            json={"workflow_id": workflow_id, "instruction": "加一个节点"},
        )
        assert audit_file.exists()
        content = audit_file.read_text(encoding="utf-8").strip()
        assert "agent.modify" in content
        assert "prompt_hash" in content


# ---------------------------------------------------------------------------
# 5. repair_count increments per repair pass
# ---------------------------------------------------------------------------

class TestRepairCount:
    def _self_loop_intent(self):
        from backend.app.schemas.workflow_intent import (
            ConnectionIntent,
            NodeIntent,
            PortRef,
            WorkflowIntent,
        )

        return WorkflowIntent(
            name="Loop",
            nodes=[NodeIntent(alias="a", kind="textInput")],
            connections=[
                ConnectionIntent(
                    source=PortRef(node="a", port="text"),
                    target=PortRef(node="a", port="text"),  # self-loop -> repaired
                ),
            ],
        )

    def test_repair_pass_increments_repair_count(self):
        from backend.app.services.agent_repair import repair_intent

        with agent_trace.trace_operation("generate", prompt="repair me") as ctx:
            result = repair_intent(self._self_loop_intent())
            assert result.repairs, "the self-loop must be repaired"
            ctx.finish(status="ok")

        detail = get_trace(ctx.trace_id)
        assert detail["repair_count"] == 1
        repair_steps = [s for s in detail["steps"] if s["kind"] == "repair"]
        assert len(repair_steps) == 1
        assert repair_steps[0]["name"].startswith("repair_pass_")

    def test_repair_count_accumulates_across_passes(self):
        from backend.app.services.agent_repair import repair_intent

        with agent_trace.trace_operation("generate", prompt="repair twice") as ctx:
            # two repair passes (mirrors the v2 double-attempt wrapper)
            repair_intent(self._self_loop_intent())
            repair_intent(self._self_loop_intent())
            ctx.finish(status="ok")

        detail = get_trace(ctx.trace_id)
        assert detail["repair_count"] == 2
        assert len([s for s in detail["steps"] if s["kind"] == "repair"]) == 2

    def test_direct_increment_persists(self):
        ctx = start_trace("generate", prompt="inc")
        ctx.increment_repair()
        ctx.increment_repair()
        ctx.finish(status="ok")
        assert get_trace(ctx.trace_id)["repair_count"] == 2


# ---------------------------------------------------------------------------
# 6. list_traces filters / pagination / total
# ---------------------------------------------------------------------------

class TestListTraces:
    def _make(self, kind, workflow_id=None):
        ctx = start_trace(kind, workflow_id=workflow_id, prompt=f"p-{kind}-{workflow_id}")
        ctx.add_step("parse", "structured_intent", "ok", 0, {})
        ctx.finish(status="ok")
        return ctx.trace_id

    def test_filters_by_workflow_id_and_kind(self):
        self._make("generate", "wf-1")
        self._make("modify", "wf-1")
        self._make("generate", "wf-2")

        by_wf = list_traces(workflow_id="wf-1")
        assert by_wf["total"] == 2
        assert {t["kind"] for t in by_wf["traces"]} == {"generate", "modify"}

        by_kind = list_traces(kind="generate")
        assert by_kind["total"] == 2
        assert all(t["kind"] == "generate" for t in by_kind["traces"])

        both = list_traces(workflow_id="wf-1", kind="modify")
        assert both["total"] == 1
        assert both["traces"][0]["workflow_id"] == "wf-1"

    def test_limit_offset_and_total_ignores_limit(self):
        ids = [self._make("generate", "wf-pag") for _ in range(5)]

        page = list_traces(workflow_id="wf-pag", limit=2, offset=0)
        assert len(page["traces"]) == 2
        assert page["total"] == 5  # unfiltered-by-limit count

        page2 = list_traces(workflow_id="wf-pag", limit=2, offset=2)
        assert len(page2["traces"]) == 2
        assert page2["total"] == 5

        seen = {t["trace_id"] for t in page["traces"]} | {
            t["trace_id"] for t in page2["traces"]
        }
        assert len(seen) == 4

        page3 = list_traces(workflow_id="wf-pag", limit=2, offset=4)
        assert len(page3["traces"]) == 1

    def test_summary_shape(self):
        tid = self._make("apply", "wf-shape")
        summary = list_traces(workflow_id="wf-shape")["traces"][0]
        assert summary["trace_id"] == tid
        assert summary["kind"] == "apply"
        assert summary["status"] == "ok"
        assert summary["error_code"] is None
        assert re.fullmatch(r"[0-9a-f]{64}", summary["prompt_hash"])
        assert summary["repair_count"] == 0
        assert summary["step_count"] == 1
        assert summary["duration_ms"] >= 0
        assert summary["created_at"]
        assert set(summary.keys()) == {
            "trace_id", "workflow_id", "kind", "status", "error_code",
            "prompt_hash", "provider", "model", "repair_count",
            "step_count", "duration_ms", "created_at",
        }

    def test_list_endpoint_contract(self, client):
        self._make("generate", "wf-api")
        resp = client.get("/api/agent/traces", params={"workflow_id": "wf-api"})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"traces", "total"}
        assert body["total"] == 1

    def test_list_endpoint_rejects_bad_params(self, client):
        resp = client.get("/api/agent/traces", params={"kind": "nope"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TRACE_QUERY_INVALID"

        resp = client.get("/api/agent/traces", params={"limit": 0})
        assert resp.status_code == 422

        resp = client.get("/api/agent/traces", params={"limit": 201})
        assert resp.status_code == 422

        resp = client.get("/api/agent/traces", params={"offset": -1})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. get_trace 404 on unknown id
# ---------------------------------------------------------------------------

class TestGetTrace404:
    def test_unknown_id_returns_404_envelope(self, client):
        resp = client.get("/api/agent/traces/trc-does-not-exist")
        assert resp.status_code == 404
        body = resp.json()
        assert body == {
            "error": {
                "code": "TRACE_NOT_FOUND",
                "message": body["error"]["message"],
            }
        }
        assert body["error"]["code"] == "TRACE_NOT_FOUND"
        assert isinstance(body["error"]["message"], str)

    def test_get_trace_helper_returns_none(self):
        assert get_trace("trc-missing") is None

    def test_detail_shape(self, client):
        ctx = start_trace("generate", workflow_id="wf-d", prompt="shape")
        ctx.add_step("parse", "structured_intent", "ok", 12, {"lang": "zh"})
        ctx.finish(status="ok", token_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})

        resp = client.get(f"/api/agent/traces/{ctx.trace_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["trace_id"] == ctx.trace_id
        assert detail["token_usage"] == {
            "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3,
        }
        assert detail["module_diff_summary"] is None
        step = detail["steps"][0]
        assert step["step_id"].startswith("stp-")
        assert step["seq"] == 0
        assert step["kind"] == "parse"
        assert step["name"] == "structured_intent"
        assert step["status"] == "ok"
        assert step["duration_ms"] == 12
        assert step["detail"] == {"lang": "zh"}


# ---------------------------------------------------------------------------
# 8. trace write failure does not break the agent operation
# ---------------------------------------------------------------------------

class TestTraceFailureIsolation:
    def test_generate_survives_recorder_failures(self, client, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError("trace recorder down")

        monkeypatch.setattr(agent_trace, "start_trace", _boom)
        monkeypatch.setattr(AgentTraceContext, "add_step", _boom)
        monkeypatch.setattr(AgentTraceContext, "finish", _boom)
        monkeypatch.setattr(AgentTraceContext, "increment_repair", _boom)

        resp = client.post("/api/agent/generate", json={"prompt": "trace 故障不影响生成"})
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["nodes"], "generate must still return a spec"

    def test_generate_survives_finish_failure_only(self, client, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError("finish down")

        monkeypatch.setattr(AgentTraceContext, "finish", _boom)
        resp = client.post("/api/agent/generate", json={"prompt": "finish 故障测试"})
        assert resp.status_code == 200
        assert resp.json()["nodes"]


# ---------------------------------------------------------------------------
# 9. both v1 and v2 paths produce traces
# ---------------------------------------------------------------------------

class TestV1AndV2Coverage:
    def test_v1_generate_traces(self, client):
        resp = client.post("/api/agent/generate", json={"prompt": "v1 生成路径"})
        assert resp.status_code == 200
        traces = list_traces(kind="generate")
        assert traces["total"] == 1
        assert get_trace(traces["traces"][0]["trace_id"])["steps"]

    def test_v2_generate_preview_traces(self, client):
        resp = client.post(
            "/api/agent/generate-preview-v2", json={"prompt": "v2 生成路径"}
        )
        assert resp.status_code == 200
        traces = list_traces(kind="generate")
        assert traces["total"] == 1
        detail = get_trace(traces["traces"][0]["trace_id"])
        assert detail["steps"]

    def test_v2_modify_preview_traces_and_audit(self, client, audit_file):
        gen = client.post("/api/agent/generate", json={"prompt": "v2 modify 基础"})
        workflow_id = gen.json()["id"]

        resp = client.post(
            "/api/agent/modify-preview-v2",
            json={"workflow_id": workflow_id, "instruction": "调整场景数量"},
        )
        assert resp.status_code == 200

        traces = list_traces(kind="modify")
        assert traces["total"] == 1
        assert traces["traces"][0]["workflow_id"] == workflow_id

        lines = _read_audit_lines(audit_file)
        assert any(e["event_type"] == "agent.modify" for e in lines)

    def test_v2_apply_traces_and_audit(self, client, audit_file):
        preview = client.post(
            "/api/agent/generate-preview-v2", json={"prompt": "v2 apply 流程"}
        )
        assert preview.status_code == 200
        intent = preview.json()["intent"]

        resp = client.post("/api/agent/apply-v2", json={"intent": intent})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        apply_traces = list_traces(kind="apply")
        assert apply_traces["total"] == 1

        lines = _read_audit_lines(audit_file)
        assert any(e["event_type"] == "agent.apply" for e in lines)

    def test_v1_and_v2_generate_two_traces(self, client):
        assert client.post("/api/agent/generate", json={"prompt": "路径 A"}).status_code == 200
        assert (
            client.post("/api/agent/generate-preview-v2", json={"prompt": "路径 B"}).status_code
            == 200
        )
        traces = list_traces(kind="generate")
        assert traces["total"] == 2
