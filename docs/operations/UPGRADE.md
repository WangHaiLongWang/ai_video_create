# ai_video_create 升级指南

本文档提供从旧版本升级到新版本的标准流程。

## 升级前准备

在执行任何升级操作之前，务必完成以下准备工作：

### 1. 备份数据库

数据库文件位于 `data/ai_video_create.db`，包含所有工作流、执行记录和模板数据。

**Windows (PowerShell)：**
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item data\ai_video_create.db "backups\ai_video_create_$timestamp.db"
```

**macOS / Linux：**
```bash
mkdir -p backups
cp data/ai_video_create.db "backups/ai_video_create_$(date +%Y%m%d_%H%M%S).db"
```

### 2. 备份资产目录

资产目录 `data/assets/` 包含生成的图片、视频和最终成品。

**Windows (PowerShell)：**
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Compress-Archive -Path data\assets -DestinationPath "backups\assets_$timestamp.zip"
```

**macOS / Linux：**
```bash
tar -czf "backups/assets_$(date +%Y%m%d_%H%M%S).tar.gz" data/assets/
```

### 3. 记录当前版本

```bash
git log --oneline -1
git describe --tags --always
```

### 4. 查看变更日志

阅读 `CHANGELOG.md` 中目标版本的变更说明，重点关注：

- **Breaking Changes**（破坏性变更）：可能导致现有工作流或配置不兼容
- **Migration**（数据库迁移）：新增的迁移文件会在启动时自动执行
- **依赖变更**：新增或升级的 Python/Node.js 依赖

## 升级步骤

### 步骤 1：停止服务

停止正在运行的后端和前端服务。

### 步骤 2：拉取最新代码

```bash
git fetch origin
git log --oneline HEAD..origin/main  # 预览将要拉入的变更
git pull origin main
```

> **提示：** 如果拉取后有合并冲突，先解决冲突再继续。

### 步骤 3：更新后端依赖

**Windows (PowerShell)：**
```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux：**
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

如果 `requirements.txt` 中新增了依赖，pip 会自动安装。如果有依赖版本冲突，可尝试：

```bash
pip install --upgrade -r requirements.txt
```

### 步骤 4：数据库迁移

数据库迁移在后端启动时**自动执行**，无需手动操作。迁移文件位于 `backend/app/db/migrations/` 目录，按编号顺序依次执行。

迁移具有以下特性：
- **幂等性**：已执行的迁移不会重复执行
- **容错性**：如果某列已存在（`duplicate column name`），会自动跳过
- **不可逆性**：当前迁移不包含回滚脚本，这也是升级前需要备份的原因

如果自动迁移失败，后端启动时会报错。此时需要检查：
1. 数据库文件是否可写
2. 磁盘空间是否充足
3. 数据库文件是否损坏

### 步骤 5：更新前端依赖

```bash
cd frontend
npm install
```

### 步骤 6：重新构建前端（生产环境）

如果需要构建生产版本：

```bash
cd frontend
npm run build
```

开发模式下（`npm run dev`）无需手动构建。

### 步骤 7：重启服务

按正常方式启动后端和前端服务（参见 [安装指南](INSTALL.md#5-启动开发服务器)）。

### 步骤 8：验证升级

1. 访问健康检查接口确认后端正常：
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```

2. 访问前端界面确认页面正常加载

3. 运行测试套件：
   ```bash
   # 后端
   cd backend && python -m pytest tests -v

   # 前端
   cd frontend && npm test
   ```

4. 确认之前的工作流和执行记录仍可访问

## 版本兼容性说明

### 数据库迁移兼容性

- 当前版本共 7 个迁移文件（`001` 至 `007`）
- 迁移只做**增操作**（新增表、新增列），不修改或删除现有结构
- 从 `0.1.0-rc.1`（Migration 006）到 `0.9.0`（Migration 007）是向前兼容的
- 回滚到旧版本时，旧版本会忽略新列，但新列中的数据会丢失

### API 向后兼容性

- REST API 遵循语义化版本控制
- 新增 API 端点不影响旧客户端
- 修改现有 API 端点时保持向后兼容（新增可选参数，不改变必填参数）

### 前端 / 后端版本匹配

- 前端和后端应使用同一版本号
- 前端 `package.json` 中的版本号和 FastAPI `app.version` 应一致
- 不匹配时可能导致 API 调用失败或界面异常

## 回滚

如果升级后遇到严重问题需要回滚，请参阅 [回滚指南](ROLLBACK.md)。

## 常见升级问题

### pip 安装失败

**症状：** `pip install -r requirements.txt` 报错

**解决：** 确认虚拟环境已激活，Python 版本为 3.12+：
```bash
python --version
pip --version
```

### 数据库迁移报错

**症状：** 后端启动时数据库相关错误

**解决：** 使用升级前的备份恢复数据库，参见 [回滚指南](ROLLBACK.md)。

### 前端构建失败

**症状：** `npm run build` 报 TypeScript 错误

**解决：** 确认 Node.js 版本为 20+，删除 `node_modules` 后重新安装：
```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

**Windows (PowerShell)：**
```powershell
cd frontend
Remove-Item -Recurse -Force node_modules
npm install
npm run build
```
