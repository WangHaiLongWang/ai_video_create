-- 013_provider_configs: named provider configurations.
-- Secrets remain in the encrypted configs key/value store; this table only
-- contains references and non-sensitive connection metadata.
CREATE TABLE IF NOT EXISTS provider_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    provider_type TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    default_capabilities_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_provider_configs_type ON provider_configs(provider_type);
CREATE INDEX IF NOT EXISTS idx_provider_configs_enabled ON provider_configs(enabled);
