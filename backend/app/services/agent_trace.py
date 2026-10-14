"""Agent Trace recorder — persist agent generate/modify/apply traces.

Mirrors :mod:`backend.app.services.event_bus`: every write goes to the database
first.  A trace is one agent operation (``generate`` / ``modify`` / ``apply``)
with an ordered list of steps (``parse`` / ``intent`` / ``fallback`` / ``tool``
/ ``repair`` / ``compile`` / ``validate``).

Hard rules (HARD-403):
- The raw user prompt is NEVER persisted — only ``prompt_hash`` (SHA-256 hex).
- Everything persisted passes through :mod:`backend.app.security.secrets_mask`
  first (``prompt_hash`` itself is a digest we computed, so it is stored as-is).
- Trace writes must never raise into the agent call path — failures are
  swallowed and logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

from backend.app.db.connection import get_connection
from backend.app.security.secrets_mask import mask_secrets

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

TRACE_KIND_GENERATE = "generate"
TRACE_KIND_MODIFY = "modify"
TRACE_KIND_APPLY = "apply"
TRACE_KINDS = (TRACE_KIND_GENERATE, TRACE_KIND_MODIFY, TRACE_KIND_APPLY)

STEP_KINDS = ("parse", "intent", "fallback", "tool", "repair", "compile", "validate")
STEP_STATUSES = ("ok", "error", "skipped")

STATUS_OK = "ok"
STATUS_ERROR = "error"

AUDIT_GENERATE = "agent.generate"
AUDIT_MODIFY = "agent.modify"
AUDIT_APPLY = "agent.apply"

#: Keys whose values are digests/ids we computed ourselves (never secret
#: material).  ``mask_secrets`` would destroy a 64-char SHA-256 hex via its
#: generic HEX_TOKEN rule, so these keys are exempted from value masking.
_HASH_KEYS = frozenset({"prompt_hash"})


# ---------------------------------------------------------------------------
# Redaction helpers
# ---------------------------------------------------------------------------

def compute_prompt_hash(prompt: str | None) -> str:
    """Return the SHA-256 hex digest of the prompt (empty string if None)."""
    return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()


def redact_value(value: Any) -> Any:
    """Recursively redact secrets in a JSON-able value via ``mask_secrets``.

    Every string passes through :func:`mask_secrets` except values stored
    under ``prompt_hash`` keys (digests we computed — masking would corrupt
    them).  Non-JSON types are coerced with ``str``.
    """
    if isinstance(value, str):
        return mask_secrets(value)
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, item in value.items():
            if key in _HASH_KEYS and isinstance(item, str):
                out[key] = item
            else:
                out[key] = redact_value(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return mask_secrets(str(value))


def redact_to_json_text(value: Any) -> str | None:
    """Redact *value* and serialize it as a JSON text column payload."""
    if value is None:
        return None
    try:
        return json.dumps(redact_value(value), ensure_ascii=False, default=str)
    except Exception:  # pragma: no cover - defensive
        return json.dumps({"_text": mask_secrets(str(value))}, ensure_ascii=False)


def _load_json_text(text: str | None) -> Any:
    """Parse a redacted JSON column back into a Python value."""
    if text is None:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return {"_text": text}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Diff summary helpers
# ---------------------------------------------------------------------------

def build_diff_summary(
    *,
    added: int = 0,
    removed: int = 0,
    updated: int = 0,
    modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the pinned ``module_diff_summary`` shape."""
    return {
        "added": int(added),
        "removed": int(removed),
        "updated": int(updated),
        "modules": list(modules or []),
    }


def _module_id_of(node: Any) -> str | None:
    """Best-effort moduleId extraction from a WorkflowNode / node dict."""
    data = node.get("data") if isinstance(node, dict) else getattr(node, "data", None)
    if data is None:
        return None
    if isinstance(data, dict):
        return (
            data.get("moduleId")
            or data.get("module_id")
            or (data.get("config") or {}).get("moduleId")
            or (data.get("config") or {}).get("module_id")
        )
    return (
        getattr(data, "module_id", None)
        or getattr(data, "moduleId", None)
        or (getattr(data, "config", None) or {}).get("moduleId")
    )


def summarize_graph_patch(patch: Any) -> dict[str, Any]:
    """Summarise a GraphPatch into the pinned ``module_diff_summary`` shape."""
    add_nodes = list(getattr(patch, "add_nodes", []) or [])
    remove_nodes = list(getattr(patch, "remove_nodes", []) or [])
    update_nodes = list(getattr(patch, "update_nodes", []) or [])

    modules: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(node: Any, change_type: str) -> None:
        mid = _module_id_of(node)
        if mid and mid not in seen:
            seen.add(mid)
            modules.append({"module_id": mid, "type": change_type})

    for node in add_nodes:
        _add(node, "added")
    for node in update_nodes:
        _add(node, "updated")
    # remove_nodes are node ids (not nodes) — module identity is unknown there.

    return build_diff_summary(
        added=len(add_nodes),
        removed=len(remove_nodes),
        updated=len(update_nodes),
        modules=modules,
    )


def summarize_module_diffs(module_diffs: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Summarise ``compute_module_diffs`` entries into the pinned shape."""
    added = removed = updated = 0
    modules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in module_diffs or []:
        if not isinstance(entry, dict):
            continue
        type_ = str(entry.get("type") or "")
        if type_ == "added":
            added += 1
        elif type_ == "removed":
            removed += 1
        else:
            updated += 1
        mid = entry.get("moduleId") or entry.get("module_id")
        if mid and mid not in seen:
            seen.add(mid)
            modules.append({
                "module_id": mid,
                "type": type_,
                "from": entry.get("from"),
                "to": entry.get("to"),
            })
    return build_diff_summary(added=added, removed=removed, updated=updated, modules=modules)


# ---------------------------------------------------------------------------
# Trace context
# ---------------------------------------------------------------------------

class AgentTraceContext:
    """In-progress trace recorder.  All writes swallow failures."""

    def __init__(
        self,
        trace_id: str,
        kind: str,
        workflow_id: str | None,
        prompt_hash: str,
        provider: str | None,
        model: str | None,
        started_perf: float,
    ) -> None:
        self.trace_id = trace_id
        self.kind = kind
        self.workflow_id = workflow_id
        self.prompt_hash = prompt_hash
        self.provider = provider
        self.model = model
        self.repair_count = 0
        self._started_perf = started_perf
        self._seq = 0
        self._finished = False
        self._status = STATUS_OK
        self._error_code: str | None = None
        self._module_diff_summary: dict[str, Any] | None = None
        self._token_usage: dict[str, Any] | None = None

    # -- steps ---------------------------------------------------------

    def add_step(
        self,
        kind: str,
        name: str,
        status: str = STATUS_OK,
        duration_ms: int = 0,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append one step row (redacted).  Never raises."""
        try:
            conn = get_connection()
            step_id = f"stp-{uuid.uuid4().hex[:12]}"
            seq = self._seq
            self._seq += 1
            conn.execute(
                "INSERT INTO agent_trace_steps "
                "(step_id, trace_id, seq, kind, name, status, duration_ms, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    step_id,
                    self.trace_id,
                    seq,
                    kind,
                    mask_secrets(name or ""),
                    status if status in STEP_STATUSES else STATUS_OK,
                    int(duration_ms or 0),
                    redact_to_json_text(detail),
                ),
            )
            conn.commit()
        except Exception as exc:
            logger.error("agent trace add_step failed: %s", exc)

    def increment_repair(self, n: int = 1) -> None:
        """Bump the repair counter (persisted on finish).  Never raises."""
        try:
            self.repair_count += max(1, int(n))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("agent trace increment_repair failed: %s", exc)

    # -- finish --------------------------------------------------------

    def finish(
        self,
        status: str | None = None,
        error_code: str | None = None,
        module_diff_summary: dict[str, Any] | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> None:
        """Close the trace row.  Idempotent.  Never raises."""
        if self._finished:
            return
        self._finished = True
        try:
            if status is not None:
                self._status = status
            if error_code is not None:
                self._error_code = error_code
            if module_diff_summary is not None:
                self._module_diff_summary = module_diff_summary
            if token_usage is not None:
                self._token_usage = token_usage

            duration_ms = int((time.perf_counter() - self._started_perf) * 1000)
            conn = get_connection()
            conn.execute(
                "UPDATE agent_traces SET status = ?, error_code = ?, repair_count = ?, "
                "duration_ms = ?, module_diff_summary = ?, token_usage = ? "
                "WHERE trace_id = ?",
                (
                    self._status if self._status in (STATUS_OK, STATUS_ERROR) else STATUS_OK,
                    mask_secrets(self._error_code) if self._error_code else None,
                    int(self.repair_count),
                    duration_ms,
                    redact_to_json_text(self._module_diff_summary),
                    redact_to_json_text(self._token_usage),
                    self.trace_id,
                ),
            )
            conn.commit()
        except Exception as exc:
            logger.error("agent trace finish failed: %s", exc)

    def set_status(self, status: str, error_code: str | None = None) -> None:
        """Record the final status for a soft (non-raising) failure."""
        self._status = status
        if error_code is not None:
            self._error_code = error_code

    def set_module_diff_summary(self, summary: dict[str, Any] | None) -> None:
        self._module_diff_summary = summary

    def set_token_usage(self, usage: dict[str, Any] | None) -> None:
        self._token_usage = usage

    # -- context manager ----------------------------------------------

    def __enter__(self) -> "AgentTraceContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self._finished:
            if exc is not None:
                self.finish(
                    status=STATUS_ERROR,
                    error_code=self._error_code or type(exc).__name__,
                )
            else:
                self.finish()
        return False


class NullAgentTrace:
    """No-op trace used when recording is unavailable or start_trace failed."""

    trace_id: str = ""
    kind: str = ""
    workflow_id: str | None = None
    prompt_hash: str = ""
    provider: str | None = None
    model: str | None = None
    repair_count: int = 0

    def add_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def increment_repair(self, n: int = 1) -> None:
        return None

    def finish(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set_module_diff_summary(self, *args: Any, **kwargs: Any) -> None:
        return None

    def set_token_usage(self, *args: Any, **kwargs: Any) -> None:
        return None

    def __enter__(self) -> "NullAgentTrace":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False


_NULL_TRACE = NullAgentTrace()

# Current trace for step hooks in friend services (parser/repair/compiler/tools)
_current_trace: ContextVar[AgentTraceContext | NullAgentTrace | None] = ContextVar(
    "agent_trace_current", default=None
)


def current_trace() -> AgentTraceContext | NullAgentTrace | None:
    """Return the trace bound to the current context, if any."""
    return _current_trace.get()


# ---------------------------------------------------------------------------
# Lifecycle — every entry point is exception-safe
# ---------------------------------------------------------------------------

def start_trace(
    kind: str,
    workflow_id: str | None = None,
    prompt: str | None = "",
    provider: str | None = None,
    model: str | None = None,
) -> AgentTraceContext | NullAgentTrace:
    """Open a trace row (``prompt_hash`` only — the prompt itself is dropped)."""
    try:
        trace_id = f"trc-{uuid.uuid4().hex[:12]}"
        prompt_hash = compute_prompt_hash(prompt)
        created_at = _now_iso()
        conn = get_connection()
        conn.execute(
            "INSERT INTO agent_traces "
            "(trace_id, workflow_id, kind, status, error_code, prompt_hash, provider, model, "
            " repair_count, duration_ms, module_diff_summary, token_usage, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                workflow_id,
                kind,
                STATUS_OK,
                None,
                prompt_hash,
                mask_secrets(provider) if provider else None,
                mask_secrets(model) if model else None,
                0,
                0,
                None,
                None,
                created_at,
            ),
        )
        conn.commit()
        return AgentTraceContext(
            trace_id=trace_id,
            kind=kind,
            workflow_id=workflow_id,
            prompt_hash=prompt_hash,
            provider=provider,
            model=model,
            started_perf=time.perf_counter(),
        )
    except Exception as exc:
        logger.error("agent trace start_trace failed: %s", exc)
        return _NULL_TRACE


@contextmanager
def trace_operation(
    kind: str,
    workflow_id: str | None = None,
    prompt: str | None = "",
    provider: str | None = None,
    model: str | None = None,
) -> Iterator[AgentTraceContext | NullAgentTrace]:
    """Trace one agent operation.

    Binds the trace as the current trace so friend services can add steps.
    The trace finishes with ``ok`` on clean exit (or the status set via
    ``set_status``) and with ``error`` when an exception escapes.  Trace
    failures never propagate into the wrapped operation.
    """
    try:
        ctx = start_trace(
            kind, workflow_id=workflow_id, prompt=prompt, provider=provider, model=model
        )
    except Exception as exc:
        logger.error("agent trace start failed: %s", exc)
        ctx = _NULL_TRACE
    token = None
    try:
        token = _current_trace.set(ctx)
    except Exception:  # pragma: no cover - defensive
        token = None
    try:
        yield ctx
    except Exception as exc:
        pre_set = getattr(ctx, "_error_code", None)
        safe_finish(ctx, status=STATUS_ERROR, error_code=pre_set or type(exc).__name__)
        raise
    else:
        safe_finish(ctx)
    finally:
        if token is not None:
            try:
                _current_trace.reset(token)
            except Exception:  # pragma: no cover - cross-context reset
                try:
                    _current_trace.set(None)
                except Exception:
                    pass


def safe_add_step(
    trace: AgentTraceContext | NullAgentTrace | None,
    kind: str,
    name: str,
    status: str = STATUS_OK,
    duration_ms: int = 0,
    detail: dict[str, Any] | None = None,
) -> None:
    """Add a step to *trace* (or the current trace) without ever raising."""
    try:
        target = trace if trace is not None else current_trace()
        if target is not None:
            target.add_step(kind, name, status=status, duration_ms=duration_ms, detail=detail)
    except Exception as exc:
        logger.error("agent trace safe_add_step failed: %s", exc)


def safe_increment_repair(
    trace: AgentTraceContext | NullAgentTrace | None = None, n: int = 1
) -> None:
    """Increment repair_count on *trace* (or the current trace).  Never raises."""
    try:
        target = trace if trace is not None else current_trace()
        if target is not None:
            target.increment_repair(n)
    except Exception as exc:
        logger.error("agent trace safe_increment_repair failed: %s", exc)


def safe_finish(
    trace: AgentTraceContext | NullAgentTrace | None,
    status: str | None = None,
    error_code: str | None = None,
    module_diff_summary: dict[str, Any] | None = None,
    token_usage: dict[str, Any] | None = None,
) -> None:
    """Finish *trace* without ever raising."""
    try:
        if trace is not None:
            trace.finish(
                status=status,
                error_code=error_code,
                module_diff_summary=module_diff_summary,
                token_usage=token_usage,
            )
    except Exception as exc:
        logger.error("agent trace safe_finish failed: %s", exc)


# ---------------------------------------------------------------------------
# Audit bridge (audit_logger was previously dead code — wire it in here)
# ---------------------------------------------------------------------------

def emit_agent_audit(
    event_type: str,
    *,
    prompt_hash: str,
    module_diff_summary: dict[str, Any] | None = None,
    repair_count: int = 0,
    trace_id: str | None = None,
    endpoint: str = "",
) -> None:
    """Emit one ``audit_logger`` event for modify/apply.  Never raises."""
    try:
        from backend.app.services.audit_logger import audit_logger

        detail = redact_value({
            "prompt_hash": prompt_hash,
            "module_diff_summary": module_diff_summary,
            "repair_count": int(repair_count or 0),
            "trace_id": trace_id or "",
        })
        audit_logger.log_event(
            event_type=event_type,
            endpoint=endpoint,
            detail=detail,
            severity="info",
        )
    except Exception as exc:
        logger.error("agent trace emit_agent_audit failed: %s", exc)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _summary_from_row(row: Any, step_count: int | None = None) -> dict[str, Any]:
    """Build a TraceSummary dict from an agent_traces row (redacted)."""
    data = dict(row)
    if step_count is None:
        step_count = int(data.get("step_count") or 0)
    return {
        "trace_id": data["trace_id"],
        "workflow_id": data["workflow_id"],
        "kind": data["kind"],
        "status": data["status"],
        "error_code": mask_secrets(data["error_code"]) if data.get("error_code") else None,
        "prompt_hash": data["prompt_hash"],
        "provider": mask_secrets(data["provider"]) if data.get("provider") else None,
        "model": mask_secrets(data["model"]) if data.get("model") else None,
        "repair_count": int(data.get("repair_count") or 0),
        "step_count": int(step_count or 0),
        "duration_ms": int(data.get("duration_ms") or 0),
        "created_at": data["created_at"],
    }


def _step_from_row(row: Any) -> dict[str, Any]:
    data = dict(row)
    detail = _load_json_text(data.get("detail"))
    if detail is None:
        detail = {}
    elif not isinstance(detail, dict):
        detail = {"_text": str(detail)}
    return {
        "step_id": data["step_id"],
        "seq": int(data.get("seq") or 0),
        "kind": data["kind"],
        "name": data["name"],
        "status": data["status"],
        "duration_ms": int(data.get("duration_ms") or 0),
        "detail": redact_value(detail),
    }


def list_traces(
    workflow_id: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List trace summaries.  ``total`` ignores limit/offset but honours filters.

    Returns ``{"traces": [TraceSummary], "total": int}``.  Never raises into
    the caller for data issues — DB failures propagate as empty results.
    """
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))

    where: list[str] = []
    params: list[Any] = []
    if workflow_id is not None:
        where.append("workflow_id = ?")
        params.append(workflow_id)
    if kind is not None:
        where.append("kind = ?")
        params.append(kind)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = get_connection()
    total = conn.execute(
        f"SELECT COUNT(*) AS n FROM agent_traces {where_sql}", params
    ).fetchone()["n"]

    rows = conn.execute(
        f"SELECT t.*, "
        f"(SELECT COUNT(*) FROM agent_trace_steps s WHERE s.trace_id = t.trace_id) AS step_count "
        f"FROM agent_traces t {where_sql} "
        f"ORDER BY t.created_at DESC, t.rowid DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()

    return {
        "traces": [_summary_from_row(row) for row in rows],
        "total": int(total),
    }


def get_trace(trace_id: str) -> dict[str, Any] | None:
    """Return a TraceDetail dict for *trace_id*, or None when unknown."""
    conn = get_connection()
    row = conn.execute(
        "SELECT t.*, "
        "(SELECT COUNT(*) FROM agent_trace_steps s WHERE s.trace_id = t.trace_id) AS step_count "
        "FROM agent_traces t WHERE t.trace_id = ?",
        (trace_id,),
    ).fetchone()
    if row is None:
        return None

    step_rows = conn.execute(
        "SELECT * FROM agent_trace_steps WHERE trace_id = ? ORDER BY seq",
        (trace_id,),
    ).fetchall()

    summary = _summary_from_row(row)
    summary["steps"] = [_step_from_row(r) for r in step_rows]
    summary["module_diff_summary"] = _load_json_text(row["module_diff_summary"])
    summary["token_usage"] = _load_json_text(row["token_usage"])
    return summary
