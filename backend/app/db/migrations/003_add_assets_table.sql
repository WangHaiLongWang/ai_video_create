-- 003_add_assets_table: 添加 assets 表，支持资产血缘追踪

CREATE TABLE IF NOT EXISTS assets (
    id                  TEXT PRIMARY KEY,
    execution_id        TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    scene_id            TEXT,
    asset_type          TEXT NOT NULL,           -- text / image / video / final
    file_path           TEXT NOT NULL,
    file_size           INTEGER NOT NULL DEFAULT 0,
    mime_type           TEXT NOT NULL DEFAULT '',
    provider            TEXT NOT NULL DEFAULT '',
    model               TEXT NOT NULL DEFAULT '',
    source_asset_ids    TEXT NOT NULL DEFAULT '[]',  -- JSON array of upstream asset IDs
    metadata            TEXT NOT NULL DEFAULT '{}',   -- JSON object for extra info
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assets_execution ON assets(execution_id);
CREATE INDEX IF NOT EXISTS idx_assets_node ON assets(node_id);
CREATE INDEX IF NOT EXISTS idx_assets_task ON assets(task_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
