-- 007_add_retry_columns: 为 tasks 表添加 error_code 和 next_retry_at 列，支持指数退避重试

-- 添加 error_code 列，用于错误分类
ALTER TABLE tasks ADD COLUMN error_code TEXT;

-- 添加 next_retry_at 列，用于退避调度（ISO 8601 时间戳）
ALTER TABLE tasks ADD COLUMN next_retry_at TEXT;

-- 添加 idempotency_key 列，用于幂等键防止重复执行
ALTER TABLE tasks ADD COLUMN idempotency_key TEXT;

-- 索引：支持按 next_retry_at 查询可重试任务
CREATE INDEX IF NOT EXISTS idx_tasks_next_retry_at ON tasks(next_retry_at);

-- 索引：支持按 idempotency_key 去重查询
CREATE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key);
