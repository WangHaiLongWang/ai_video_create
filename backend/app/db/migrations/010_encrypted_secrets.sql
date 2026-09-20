-- 010_encrypted_secrets: Add configs table with encrypted secret support
-- Provides a persistent key-value store for API keys and provider credentials
-- that can be optionally encrypted at rest using AES-256-GCM.

-- Key-value config table
CREATE TABLE IF NOT EXISTS configs (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL DEFAULT '',
    is_encrypted INTEGER NOT NULL DEFAULT 0,  -- 1 = value is AES-256-GCM encrypted
    encrypted_at TEXT,                         -- ISO-8601 timestamp when encryption was applied
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Index for quick lookup of encrypted values (e.g. key rotation)
CREATE INDEX IF NOT EXISTS idx_configs_is_encrypted ON configs(is_encrypted);
