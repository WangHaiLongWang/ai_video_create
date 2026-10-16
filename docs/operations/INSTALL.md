# ai_video_create 安装指南

本文档提供从零开始安装和配置 ai_video_create 的完整步骤。

## 前提条件

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.12+ | 后端运行时，需包含 pip |
| Node.js | 20+ | 前端构建，需包含 npm |
| FFmpeg | 4+ | 可选，用于视频拼接合成 |
| Git | 2.0+ | 版本控制 |

### 安装 Python

**Windows：**
从 [python.org](https://www.python.org/downloads/) 下载 Python 3.12+ 安装包，安装时勾选 "Add Python to PATH"。

**macOS：**
```bash
brew install python@3.12
```

**Linux (Ubuntu/Debian)：**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

### 安装 Node.js

**Windows / macOS / Linux：**
推荐使用 [nvm](https://github.com/nvm-sh/nvm) 管理 Node.js 版本：
```bash
nvm install 20
nvm use 20
```

或从 [nodejs.org](https://nodejs.org/) 下载 LTS 版本安装包。

验证安装：
```bash
node --version   # 应显示 v20.x.x 或更高
npm --version    # 应显示 10.x.x 或更高
```

### 安装 FFmpeg（可选）

FFmpeg 用于将视频片段拼接为最终视频。不安装 FFmpeg 时图片和视频生成节点仍可运行，仅最终合成步骤会跳过。

**Windows：**
```powershell
# 使用 winget
winget install FFmpeg

# 或从 https://ffmpeg.org/download.html 下载，解压后将 bin 目录加入 PATH
```

**macOS：**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian)：**
```bash
sudo apt install ffmpeg
```

**Linux (CentOS/RHEL)：**
```bash
sudo yum install epel-release
sudo yum install ffmpeg
# 或使用 RPM Fusion 仓库
```

验证安装：
```bash
ffmpeg -version
```

## 安装步骤

### 1. 克隆仓库

```bash
git clone <repo-url>
cd ai_video_create
```

### 2. 后端安装

**Windows (PowerShell)：**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

**macOS / Linux：**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

> **注意：** 如果 `pip install` 报错权限不足，不要使用 `sudo pip install`，确保虚拟环境已激活后再试。

### 3. 前端安装

```bash
cd frontend
npm install
cd ..
```

### 4. 配置环境变量

复制示例配置文件并根据需要修改：

**Windows (PowerShell)：**
```powershell
Copy-Item .env.example .env
notepad .env
```

**macOS / Linux：**
```bash
cp .env.example .env
# 使用你喜欢的编辑器修改 .env
nano .env
```

> **重要：** `.env` 文件包含 API Key 等敏感信息，已添加到 `.gitignore`，切勿提交到版本控制。

### 5. 启动开发服务器

需要同时启动后端和前端两个服务。

**Windows (PowerShell)：**

终端 1 — 启动后端：
```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端 2 — 启动前端：
```powershell
cd frontend
npm run dev
```

**macOS / Linux：**

终端 1 — 启动后端：
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端 2 — 启动前端：
```bash
cd frontend
npm run dev
```

### 6. 验证安装

启动后访问以下地址确认服务正常：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://127.0.0.1:5173 | React 应用 |
| API 文档 | http://127.0.0.1:8000/docs | FastAPI Swagger UI |
| 健康检查 | http://127.0.0.1:8000/api/health | 应返回 `{"status": "ok"}` |

运行测试套件确认环境正确：

```bash
# 后端测试
cd backend
python -m pytest tests -v

# 前端测试
cd frontend
npm test

# TypeScript 类型检查
npm run typecheck

# 前端构建
npm run build
```

## 配置参考

所有环境变量均以 `AI_VIDEO_` 为前缀。完整配置项参见 `.env.example`。

### Provider 配置

项目支持按能力（LLM / 图像 / 视频）独立选择 Provider：

| 环境变量 | 可选值 | 默认值 | 说明 |
|---------|-------|-------|------|
| `AI_VIDEO_DEFAULT_LLM_PROVIDER` | `mock` / `ollama` / `openai` / `openai_compat` | `mock` | 文本生成 Provider |
| `AI_VIDEO_DEFAULT_IMAGE_PROVIDER` | `mock` / `comfyui` / `openai` / `dashscope` | `mock` | 图像生成 Provider |
| `AI_VIDEO_DEFAULT_VIDEO_PROVIDER` | `mock` / `comfyui` / `wan3` | `mock` | 视频生成 Provider |

#### Ollama Provider

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_OLLAMA_API_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `AI_VIDEO_OLLAMA_MODEL` | `llama3.2` | 使用的模型 |

#### OpenAI Provider

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_OPENAI_API_KEY` | （空） | API Key |
| `AI_VIDEO_OPENAI_API_URL` | `https://api.openai.com/v1` | API 地址 |
| `AI_VIDEO_OPENAI_MODEL` | `gpt-4` | 文本模型 |
| `AI_VIDEO_OPENAI_IMAGE_MODEL` | `dall-e-3` | 图像模型 |
| `AI_VIDEO_OPENAI_IMAGE_SIZE` | `1792x1024` | 图像尺寸 |

#### OpenAI Compatible Provider (默认预设: Xiaomi MiMo)

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_OPENAI_COMPAT_NAME` | `Xiaomi MiMo` | 显示名称 |
| `AI_VIDEO_OPENAI_COMPAT_API_URL` | `https://api.xiaomimimo.com/v1` | API 地址 |
| `AI_VIDEO_OPENAI_COMPAT_API_KEY` | （空） | API Key |
| `AI_VIDEO_OPENAI_COMPAT_MODEL` | `mimo-v2.5-pro` | 模型名称 |
| `AI_VIDEO_OPENAI_COMPAT_AUTH_HEADER` | `api-key` | 认证 Header 名 |
| `AI_VIDEO_OPENAI_COMPAT_AUTH_SCHEME` | （空） | 认证方案前缀 |
| `AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS` | `4096` | 最大 Token 数 |
| `AI_VIDEO_OPENAI_COMPAT_TEMPERATURE` | `1.0` | 温度 |
| `AI_VIDEO_OPENAI_COMPAT_TOP_P` | `0.95` | Top-P |
| `AI_VIDEO_OPENAI_COMPAT_TIMEOUT` | `120` | 超时秒数 |

#### DashScope Provider (Qwen Image)

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_DASHSCOPE_API_URL` | `https://dashscope.aliyuncs.com/api/v1` | API 地址 |
| `AI_VIDEO_DASHSCOPE_API_KEY` | （空） | API Key |
| `AI_VIDEO_DASHSCOPE_IMAGE_MODEL` | `qwen-image-3.0` | 图像模型 |
| `AI_VIDEO_DASHSCOPE_IMAGE_SIZE` | `1280x720` | 图像尺寸 |
| `AI_VIDEO_DASHSCOPE_USE_ASYNC` | `false` | 是否异步 |
| `AI_VIDEO_DASHSCOPE_PROMPT_EXTEND` | `true` | 提示词扩展 |
| `AI_VIDEO_DASHSCOPE_ENABLE_THINKING` | `true` | 启用思考模式 |

#### Wan3 Video Provider

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_WAN3_API_URL` | `https://dashscope.aliyuncs.com/api/v1` | API 地址 |
| `AI_VIDEO_WAN3_API_KEY` | （空） | API Key |
| `AI_VIDEO_WAN3_MODEL` | `wan3.0-video` | 模型名称 |
| `AI_VIDEO_WAN3_RESOLUTION` | `480P` | 分辨率 (480P/720P/1080P) |
| `AI_VIDEO_WAN3_RATIO` | `adaptive` | 宽高比 |
| `AI_VIDEO_WAN3_DURATION` | `5` | 视频时长（秒） |
| `AI_VIDEO_WAN3_AUDIO` | `true` | 是否包含音频 |
| `AI_VIDEO_WAN3_TIMEOUT` | `1800` | 轮询超时（秒） |

#### ComfyUI Provider

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_COMFYUI_API_URL` | `http://localhost:8188` | ComfyUI 服务地址 |
| `AI_VIDEO_COMFYUI_CHECKPOINT` | `sd_xl_base_1.0.safetensors` | 模型 Checkpoint |

### 存储配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_ASSET_DIR` | `data/assets` | 资产文件存储目录 |
| `AI_VIDEO_FFMPEG_PATH` | `ffmpeg` | FFmpeg 可执行文件路径 |

### Worker 配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_WORKER_POLL_INTERVAL` | `0.5` | Worker 轮询间隔（秒） |
| `AI_VIDEO_WORKER_LEASE_SECONDS` | `30` | Worker 租约时长（秒） |
| `AI_VIDEO_WORKER_COUNT` | `1` | Worker 数量 (1-8) |

### 数据库配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_DB_PATH` | `data/ai_video_create.db` | SQLite 数据库文件路径 |

### 服务器配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `AI_VIDEO_HOST` | `127.0.0.1` | 监听地址 |
| `AI_VIDEO_PORT` | `8000` | 监听端口 |
| `AI_VIDEO_DEBUG` | `false` | 调试模式 |

## 平台特定注意事项

### Windows

- 激活虚拟环境时，如果遇到执行策略错误：
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
- 路径分隔符使用反斜杠 `\`，但 Git Bash 和 Python 内部使用正斜杠 `/`
- 如果 FFmpeg 安装后无法识别，确认其 `bin` 目录已加入系统 PATH

### macOS

- 如果使用 Homebrew 安装的 Python，可能需要使用 `python3` 而非 `python`
- FFmpeg 通过 Homebrew 安装后自动可用
- Apple Silicon (M1/M2/M3) 设备直接支持，无需 Rosetta

### Linux

- 部分发行版需要安装 `python3-venv` 包：
  ```bash
  sudo apt install python3.12-venv  # Ubuntu
  ```
- 如果 `uvicorn` 安装失败，确认已安装 `gcc` 和 Python 开发头文件：
  ```bash
  sudo apt install build-essential python3-dev
  ```
