-- 002_add_result_column: 为 tasks 表添加 result 列，支持执行结果持久化
-- 注意：SQLite 不支持 ALTER TABLE IF NOT EXISTS，需要在 Python 中检查列是否存在再执行

-- tasks 表添加 result 列
ALTER TABLE tasks ADD COLUMN result_json TEXT DEFAULT '{}';

-- executions 表添加 task_count 和 completed_count 用于收敛
ALTER TABLE executions ADD COLUMN task_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE executions ADD COLUMN completed_count INTEGER NOT NULL DEFAULT 0;
