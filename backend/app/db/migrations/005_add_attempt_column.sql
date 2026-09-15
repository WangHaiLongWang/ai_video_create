-- 005_add_attempt_column: 为 tasks 表添加 attempt 列，支持重试逻辑

ALTER TABLE tasks ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0;
