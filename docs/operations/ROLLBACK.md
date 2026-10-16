# ai_video_create 回滚指南

本文档提供在升级后遇到严重问题时回滚到旧版本的标准流程。

## 何时需要回滚

以下情况应考虑回滚：

- **严重 Bug**：新版本引入了影响核心功能的 Bug
- **性能退化**：新版本导致明显性能下降（如执行超时、内存溢出）
- **数据损坏风险**：新版本的数据库迁移可能导致数据异常
- **兼容性问题**：新版本与现有工作流或配置不兼容

在决定回滚前，先尝试：
1. 查看错误日志定位问题
2. 检查是否有简单的配置修复方案
3. 确认问题不是由环境变更引起

## 回滚步骤

### 步骤 1：停止服务

停止所有正在运行的后端和前端服务。

### 步骤 2：恢复数据库

使用升级前创建的备份恢复数据库。

**Windows (PowerShell)：**
```powershell
# 查看可用备份
Get-ChildItem backups\*.db | Sort-Object LastWriteTime -Descending

# 恢复指定备份
Copy-Item "backups\ai_video_create_20260916_143000.db" data\ai_video_create.db -Force
```

**macOS / Linux：**
```bash
# 查看可用备份
ls -lt backups/*.db

# 恢复指定备份
cp backups/ai_video_create_20260916_143000.db data/ai_video_create.db
```

> **重要：** 确认后端服务已停止后再恢复数据库，避免文件锁定冲突。

### 步骤 3：恢复资产（如需要）

如果升级过程中修改或删除了资产文件：

**Windows (PowerShell)：**
```powershell
# 恢复资产目录
Remove-Item -Recurse -Force data\assets
Expand-Archive -Path "backups\assets_20260916_143000.zip" -DestinationPath data\
```

**macOS / Linux：**
```bash
# 恢复资产目录
rm -rf data/assets
tar -xzf "backups/assets_20260916_143000.tar.gz" -C .
```

### 步骤 4：检出旧版本

检出目标版本的代码：

```bash
# 查看可用的版本标签
git tag -l

# 检出特定版本
git checkout v0.9.0

# 或检出之前的 commit
git checkout <commit-hash>
```

### 步骤 5：重新安装依赖

后端和前端的依赖可能因版本不同而有差异，需要重新安装：

**Windows (PowerShell)：**
```powershell
# 后端
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 前端
cd ..\frontend
npm install
```

**macOS / Linux：**
```bash
# 后端
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 步骤 6：重新构建（生产环境）

```bash
cd frontend
npm run build
```

### 步骤 7：重启服务

按正常方式启动后端和前端服务（参见 [安装指南](INSTALL.md#5-启动开发服务器)）。

### 步骤 8：验证回滚

1. 健康检查：
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```

2. 确认返回的版本号为预期的旧版本

3. 访问前端界面确认功能正常

4. 测试关键工作流是否可以正常执行

## 数据考量

### 保留的数据

- 工作流定义和节点配置
- 执行历史和结果
- 模板数据
- 资产文件（图片、视频）
- Agent 对话记录

### 可能丢失的数据

- 新版本迁移添加的列中的数据（如 `error_code`、`next_retry_at`、`idempotency_key`）
- 新版本创建的 API Key 或 Provider 配置（如果仅存储在内存中）
- 新版本特有的工作流节点类型数据

### 迁移回滚限制

当前数据库迁移**不包含回滚脚本**。这意味着：

1. 新版本添加的表和列在回滚后仍保留在数据库中，旧版本代码会忽略它们
2. 这不会导致错误，但会占用少量额外空间
3. 如果需要完全清理，可以在回滚后手动删除新增的列/表（需要 SQLite 工具）

手动清理示例（高级操作，谨慎使用）：

```bash
# 查看当前数据库中的所有表
sqlite3 data/ai_video_create.db ".tables"

# 查看表结构
sqlite3 data/ai_video_create.db ".schema tasks"
```

## 回滚到指定版本的完整流程

以下是回滚到 `v0.9.0` 的完整命令序列：

**Windows (PowerShell)：**
```powershell
# 1. 停止服务后执行

# 2. 恢复数据库
Copy-Item "backups\ai_video_create_20260916_143000.db" data\ai_video_create.db -Force

# 3. 检出代码
git checkout v0.9.0

# 4. 重新安装后端依赖
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 5. 重新安装前端依赖
cd ..\frontend
npm install
npm run build

# 6. 重启服务
cd ..\backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**macOS / Linux：**
```bash
# 1. 停止服务后执行

# 2. 恢复数据库
cp backups/ai_video_create_20260916_143000.db data/ai_video_create.db

# 3. 检出代码
git checkout v0.9.0

# 4. 重新安装后端依赖
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# 5. 重新安装前端依赖
cd ../frontend
npm install
npm run build

# 6. 重启服务
cd ../backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 回滚后注意事项

1. **不要立即在回滚版本上执行新的升级**，先确认回滚解决了问题
2. **记录回滚原因**，以便开发团队定位和修复根因
3. **通知团队成员**当前使用的是旧版本
4. **保留升级前的备份**直到确认回滚版本稳定运行
