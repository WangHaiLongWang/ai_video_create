-- 001_initial: 创建核心数据表
-- 幂等执行：使用 IF NOT EXISTS

-- 工作流定义
CREATE TABLE IF NOT EXISTS workflows (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    schema_version TEXT NOT NULL DEFAULT '1.0',
    spec_json   TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_workflows_updated_at ON workflows(updated_at);

-- 执行记录
CREATE TABLE IF NOT EXISTS executions (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    workflow_snapshot TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending / running / completed / failed / cancelled
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_executions_workflow ON executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);

-- 任务队列
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    execution_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    kind            TEXT NOT NULL,
    label           TEXT NOT NULL DEFAULT '',
    item_key        TEXT,
    task_index      INTEGER NOT NULL DEFAULT 0,
    config_json     TEXT NOT NULL DEFAULT '{}',
    depends_on_json TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending / running / completed / failed / skipped / cancelled
    worker_id       TEXT,
    lease_until     TEXT,
    error           TEXT DEFAULT '',
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_execution ON tasks(execution_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_depends ON tasks(depends_on_json);

-- 执行事件
CREATE TABLE IF NOT EXISTS execution_events (
    id              TEXT PRIMARY KEY,
    execution_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL DEFAULT '',
    item_key        TEXT,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL,
    progress        INTEGER NOT NULL DEFAULT 0,
    message         TEXT NOT NULL DEFAULT '',
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_events_execution ON execution_events(execution_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON execution_events(timestamp);
