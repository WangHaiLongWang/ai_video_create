-- 012_agent_traces: Agent Trace persistence (HARD-403 trace + audit half).
-- One agent_traces row per generate / modify / apply operation, plus ordered
-- agent_trace_steps rows.  Prompt text is NEVER stored -- only prompt_hash
-- (SHA-256 hex).  All JSON columns are redacted via secrets_mask on write.

-- Trace header rows
CREATE TABLE IF NOT EXISTS agent_traces (
    trace_id     TEXT PRIMARY KEY,
    workflow_id  TEXT,
    kind         TEXT NOT NULL,          -- generate | modify | apply
    status       TEXT NOT NULL,          -- ok | error
    error_code   TEXT,
    prompt_hash  TEXT NOT NULL,
    provider     TEXT,
    model        TEXT,
    repair_count INTEGER NOT NULL DEFAULT 0,
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    module_diff_summary TEXT,            -- JSON, redacted
    token_usage  TEXT,                   -- JSON or NULL
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_created ON agent_traces(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_traces_workflow ON agent_traces(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_kind ON agent_traces(kind);

-- Ordered steps within a trace
CREATE TABLE IF NOT EXISTS agent_trace_steps (
    step_id     TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    kind        TEXT NOT NULL,           -- parse|intent|fallback|tool|repair|compile|validate
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,           -- ok | error | skipped
    duration_ms INTEGER NOT NULL DEFAULT 0,
    detail      TEXT,                    -- JSON, redacted
    FOREIGN KEY (trace_id) REFERENCES agent_traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_trace_steps_trace ON agent_trace_steps(trace_id);
