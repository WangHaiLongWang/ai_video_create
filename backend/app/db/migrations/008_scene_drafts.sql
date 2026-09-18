-- 008_scene_drafts: Scene draft persistence table for SQLite

-- Scene drafts table — stores serialized ScenePromptBundle with lock/override support
CREATE TABLE IF NOT EXISTS scene_drafts (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'draft',
    bundle_json TEXT NOT NULL,
    locked_scene_ids TEXT DEFAULT '[]',
    version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Index for listing drafts by workflow
CREATE INDEX IF NOT EXISTS idx_scene_drafts_workflow_id ON scene_drafts(workflow_id);

-- Index for version-based optimistic locking
CREATE INDEX IF NOT EXISTS idx_scene_drafts_version ON scene_drafts(version);
