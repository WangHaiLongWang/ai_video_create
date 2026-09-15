-- 006_add_external_job_id: 为 tasks 表添加 external_job_id 列，用于持久化外部任务 ID

-- 添加列（如果不存在）
ALTER TABLE tasks ADD COLUMN external_job_id TEXT;

-- 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_tasks_external_job_id ON tasks(external_job_id);
