-- 011_module_definitions: Module definitions storage with optimistic locking
-- Stores user-created module definitions with draft/publish/archive lifecycle.

-- Module definitions with versioning
CREATE TABLE IF NOT EXISTS module_definitions (
    id               TEXT NOT NULL,
    version          TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'draft',  -- draft, published, archived
    base_kind        TEXT NOT NULL,
    definition_json  TEXT NOT NULL,  -- full ModuleDefinition as JSON
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    published_at     TEXT,
    archived_at      TEXT,
    expected_version INTEGER NOT NULL DEFAULT 1,  -- optimistic lock
    PRIMARY KEY (id, version)
);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_module_definitions_status ON module_definitions(status);

-- Index for filtering by base_kind (capability)
CREATE INDEX IF NOT EXISTS idx_module_definitions_base_kind ON module_definitions(base_kind);

-- Module usage tracking
CREATE TABLE IF NOT EXISTS module_usage (
    workflow_id     TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    module_id       TEXT NOT NULL,
    module_version  TEXT NOT NULL,
    PRIMARY KEY (workflow_id, node_id)
);

-- Index for querying usage by module
CREATE INDEX IF NOT EXISTS idx_module_usage_module ON module_usage(module_id);
