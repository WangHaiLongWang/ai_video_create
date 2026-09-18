-- 009_add_variant_id_to_assets: Add variant_id column for variant lineage traceability

-- Add variant_id column to assets table
ALTER TABLE assets ADD COLUMN variant_id TEXT;

-- Index for querying assets by variant_id
CREATE INDEX IF NOT EXISTS idx_assets_variant ON assets(variant_id);

-- Composite index for querying by scene_id + variant_id (common query pattern)
CREATE INDEX IF NOT EXISTS idx_assets_scene_variant ON assets(scene_id, variant_id);
