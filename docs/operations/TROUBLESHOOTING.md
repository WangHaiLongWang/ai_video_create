# ai_video_create 常见问题排查

本文档列出安装、运行和开发过程中常见的问题及其解决方案。

## 目录

- [启动问题](#启动问题)
- [执行问题](#执行问题)
- [前端问题](#前端问题)
- [数据库问题](#数据库问题)
- [Windows 特有问题](#windows-特有问题)

---

## 启动问题

### 端口被占用

**症状：**
```
[ERROR] [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```

**解决方案：**

查找并终止占用端口的进程：

**Windows (PowerShell)：**
```powershell
# 查找占用 8000 端口的进程
netstat -ano | findstr :8000

# 根据 PID 终止进程（替换 <PID> 为实际值）
taskkill /PID <PID> /F

# 或使用更便捷的方式
Get-Process | Where-Object {$_.Id -eq (Get-NetTCPConnection -LocalPort 8000).OwningProcess} | Stop-Process -Force
```

**macOS / Linux：**
```bash
# 查找占用 8000 端口的进程
lsof -i :8000
# 或
ss -tlnp | grep 8000

# 终止进程
kill -9 <PID>
```

**替代方案：** 修改 `.env` 中的端口配置：
```
AI_VIDEO_PORT=8001
```

前端默认端口 5173 同理，可通过修改 `frontend/vite.config.ts` 或使用 `npm run dev -- --port 5174` 更改。

### 数据库被锁定

**症状：**
```
sqlite3.OperationalError: database is locked
```

**解决方案：**

1. 确认没有其他进程正在使用数据库：
   ```bash
   # Linux/macOS
   lsof data/ai_video_create.db

   # Windows
   handle data\ai_video_create.db
   ```

2. 删除数据库的 WAL 和 SHM 文件（SQLite WAL 模式的临时文件）：
   ```bash
   rm data/ai_video_create.db-wal data/ai_video_create.db-shm
   ```

3. 如果仍无法解决，重启后端服务。SQLite 配置了 5 秒的 `busy_timeout`，通常能自动恢复。

### 缺少依赖

**症状：**
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案：**

确认虚拟环境已激活且依赖已安装：

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

如果虚拟环境损坏，可删除后重建：
```bash
# Windows
Remove-Item -Recurse -Force backend\.venv
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# macOS / Linux
rm -rf backend/.venv
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 后端启动报 FastAPI 导入错误

**症状：**
```
ImportError: cannot import name 'xxx' from 'backend.app.xxx'
```

**解决方案：**

1. 确认在项目根目录下执行命令（而非 `backend/` 目录内）
2. 确认使用的是正确的 Python 解释器：
   ```bash
   # 应指向虚拟环境
   which python  # macOS/Linux
   where python  # Windows PowerShell
   ```
3. 重新安装依赖确保所有模块可用

---

## 执行问题

### Provider 超时

**症状：**
执行任务长时间处于 `running` 状态后超时失败。

**排查步骤：**

1. 检查 Provider 服务是否可访问：
   ```bash
   # Ollama
   curl http://localhost:11434/api/tags

   # DashScope / Wan3
   curl https://dashscope.aliyuncs.com/api/v1/models

   # ComfyUI
   curl http://localhost:8188/system_stats
   ```

2. 检查网络连接和防火墙设置

3. 检查 `.env` 中 API Key 是否正确配置

4. 调整超时参数：
   ```
   AI_VIDEO_WAN3_TIMEOUT=3600    # Wan3 视频生成超时
   AI_VIDEO_OPENAI_COMPAT_TIMEOUT=300  # LLM 超时
   ```

5. 查看后端日志获取详细错误信息

### FFmpeg 未找到

**症状：**
```
FileNotFoundError: FFmpeg not found at 'ffmpeg'
```

或视频合成步骤跳过。

**解决方案：**

1. 确认 FFmpeg 已安装：
   ```bash
   ffmpeg -version
   ```

2. 如果 FFmpeg 已安装但不在 PATH 中，在 `.env` 中指定完整路径：
   ```
   # Windows
   AI_VIDEO_FFMPEG_PATH=C:\tools\ffmpeg\bin\ffmpeg.exe

   # macOS (Homebrew)
   AI_VIDEO_FFMPEG_PATH=/opt/homebrew/bin/ffmpeg

   # Linux
   AI_VIDEO_FFMPEG_PATH=/usr/bin/ffmpeg
   ```

3. FFmpeg 是可选依赖，不安装时图片和视频生成仍可运行，仅最终视频合成步骤会跳过。

### 磁盘空间不足

**症状：**
```
OSError: [Errno 28] No space left on device
```

**解决方案：**

1. 检查磁盘使用情况：
   ```bash
   df -h          # Linux/macOS
   Get-PSDrive    # Windows PowerShell
   ```

2. 清理临时资产文件（默认保留 7 天）：
   ```bash
   # 通过 API 触发清理（需要后端运行）
   curl -X DELETE http://127.0.0.1:8000/api/assets/temp
   ```

3. 清理旧的数据库备份：
   ```bash
   ls -lt backups/ | tail -n +10  # 查看旧备份
   rm backups/ai_video_create_*.db  # 删除旧备份
   ```

4. 清理前端构建产物：
   ```bash
   rm -rf frontend/dist
   ```

### Worker 崩溃

**症状：**
执行任务卡在 `running` 状态不再推进。

**解决方案：**

1. Worker 配置了租约机制（默认 30 秒），崩溃后任务会在租约过期后自动被回收：
   ```
   AI_VIDEO_WORKER_LEASE_SECONDS=30
   ```

2. 如果任务持续卡住，重启后端服务：
   ```bash
   # 停止后重新启动
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

3. 调整 Worker 数量和轮询间隔：
   ```
   AI_VIDEO_WORKER_COUNT=2
   AI_VIDEO_WORKER_POLL_INTERVAL=0.5
   ```

---

## 前端问题

### 构建失败

**症状：**
`npm run build` 报错。

**解决方案：**

1. 清除缓存并重新安装：
   ```bash
   cd frontend
   rm -rf node_modules dist
   npm install
   npm run build
   ```

**Windows (PowerShell)：**
```powershell
cd frontend
Remove-Item -Recurse -Force node_modules, dist
npm install
npm run build
```

2. 确认 Node.js 版本为 20+：
   ```bash
   node --version
   ```

3. 如果是内存不足导致的构建失败：
   ```bash
   NODE_OPTIONS="--max-old-space-size=4096" npm run build
   ```

### TypeScript 类型错误

**症状：**
`npm run typecheck` 或 `npm run build` 报 TypeScript 类型错误。

**解决方案：**

1. 确认 `node_modules` 已安装完整：
   ```bash
   cd frontend
   npm install
   npm run typecheck
   ```

2. 如果是新拉取代码后出现的类型错误，可能需要更新 TypeScript 版本：
   ```bash
   npm install typescript@latest
   ```

3. 检查是否有未更新的类型声明：
   ```bash
   npm update @types/react @types/react-dom
   ```

### WebSocket 连接问题

**症状：**
执行状态无法实时更新，或页面显示 WebSocket 连接断开。

**排查步骤：**

1. 确认后端服务正在运行：
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```

2. 检查浏览器控制台的 WebSocket 错误信息

3. 如果使用了反向代理或 HTTPS，确认 WebSocket 升级配置正确

4. WebSocket 客户端包含自动重连机制（指数退避），通常网络恢复后会自动重连

5. 确认 CORS 配置正确（默认允许 `http://127.0.0.1:5173` 和 `http://localhost:5173`）

### 页面空白或加载失败

**解决方案：**

1. 打开浏览器开发者工具（F12）查看网络请求和控制台错误

2. 确认前端开发服务器正在运行：
   ```bash
   # 检查 Vite 输出中是否显示 "Local: http://127.0.0.1:5173"
   ```

3. 确认后端 API 可访问（前端依赖后端提供数据）

4. 如果是 CORS 错误，检查 `.env` 中 `AI_VIDEO_HOST` 配置是否与前端访问地址一致

---

## 数据库问题

### 数据库损坏恢复

**症状：**
```
sqlite3.DatabaseError: file is not a database
```

或数据库相关操作异常。

**解决方案：**

1. 首先尝试使用 SQLite 自带的完整性检查：
   ```bash
   sqlite3 data/ai_video_create.db "PRAGMA integrity_check;"
   ```

2. 如果检查失败，使用备份恢复：
   ```bash
   # 查找最近的可用备份
   ls -lt backups/*.db

   # 恢复备份
   cp backups/ai_video_create_<timestamp>.db data/ai_video_create.db
   ```

3. 如果没有可用备份，删除数据库后重建（会丢失所有数据）：
   ```bash
   rm data/ai_video_create.db data/ai_video_create.db-wal data/ai_video_create.db-shm
   # 下次启动后端时会自动创建新数据库并执行迁移
   ```

### 迁移失败

**症状：**
后端启动时数据库迁移报错。

**解决方案：**

1. 检查错误信息中提到的迁移文件编号

2. 常见原因：手动修改了数据库结构导致迁移脚本冲突

3. 解决方法：
   - 如果迁移报 `duplicate column name`，这通常是正常的（已自动跳过）
   - 如果报其他错误，检查数据库文件是否完整

4. 作为最后手段，使用备份恢复数据库后重新启动

### 锁竞争

**症状：**
执行过程中偶发 `database is locked` 错误。

**分析：**

SQLite 是单文件数据库，高并发写入时可能出现锁竞争。项目已配置：
- **WAL 模式**：允许读写并发
- **busy_timeout=5000**：等待锁释放最多 5 秒

**优化建议：**

1. 减少 Worker 数量：
   ```
   AI_VIDEO_WORKER_COUNT=1
   ```

2. 增加轮询间隔减少数据库访问频率：
   ```
   AI_VIDEO_WORKER_POLL_INTERVAL=1.0
   ```

3. 如果锁竞争频繁发生，考虑将 `busy_timeout` 调大（需修改 `backend/app/db/connection.py`）

---

## Windows 特有问题

### PowerShell 执行策略

**症状：**
```
无法加载文件 xxx\Activate.ps1，因为在此系统上禁止运行脚本。
```

**解决方案：**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

或使用 cmd.exe 代替：
```cmd
backend\.venv\Scripts\activate.bat
```

### 路径过长

**症状：**
```
OSError: [Errno 206] The filename or extension is too long
```

**解决方案：**

1. 将项目移到较短的路径下（如 `D:\Projects\avc\`）

2. 启用 Windows 长路径支持（需要管理员权限）：
   ```
   注册表：HKLM\SYSTEM\CurrentControlSet\Control\FileSystem
   设置 LongPathsEnabled = 1
   ```

### 文件路径中的空格

**症状：**
命令行中路径含空格导致命令解析错误。

**解决方案：**

使用引号包裹路径：
```powershell
cd "C:\My Projects\ai_video_create"
pip install -r "backend\requirements.txt"
```

### Python 虚拟环境激活失败

**症状：**
使用 Git Bash 时无法激活虚拟环境。

**解决方案：**

Git Bash 下使用：
```bash
source backend/.venv/Scripts/activate
```

或切换到 PowerShell / cmd 执行激活操作。

### 中文路径编码问题

**症状：**
路径中包含中文字符时出现编码错误。

**解决方案：**

1. 将项目移到纯英文路径下

2. 或设置系统区域设置支持 UTF-8：
   - 设置 > 时间和语言 > 区域 > 管理语言设置 > 更改系统区域设置
   - 勾选 "Beta: 使用 Unicode UTF-8 提供全球语言支持"
