# ai_video_create

本地优先的可视化 AI 视频工作流平台。

```text
MiMo 分镜 → Qwen Image 图片 → Wan3 视频片段 → FFmpeg 合成
```

项目提供 React Flow 编辑器、SQLite DAG 执行器、实时状态、Agent/模板、资产血缘和可替换 Provider。

## 当前阶段

项目处于内部验收前的集成收敛期，综合完成度约 70%。当前发布门禁不是全绿状态，请先阅读：

- [项目状态](docs/PROJECT-STATUS.md)
- [文档中心](docs/README.md)
- [Active 交付计划](docs/plans/active/DELIVERY-PLAN.md)

## 环境要求

- Node.js 20+（Playwright 要求；当前项目机器仍需升级）
- Python 3.12
- FFmpeg 4+，通过 `AI_VIDEO_FFMPEG_PATH` 指定
- 可选外部服务：MiMo、阿里云百炼、Ollama、ComfyUI、OpenAI

## 安装

```powershell
npm install
npm --prefix frontend install

python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

macOS/Linux 使用 `backend/.venv/bin/python`。

复制配置：

```powershell
Copy-Item .env.example .env
```

不要提交 `.env` 或 API Key。

## 启动

```powershell
npm run dev
```

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`
- Health：`http://127.0.0.1:8000/api/health`
- OpenAPI：`http://127.0.0.1:8000/docs`

## 验证

目标命令：

```powershell
npm test
npm run typecheck
npm run build
npm --prefix frontend run test:e2e:chromium
```

截至 2026-09-16，根测试、typecheck/build、完整 pytest 和 Playwright 仍有环境/配置阻断。真实结果与修复顺序见 [项目状态](docs/PROJECT-STATUS.md)。

## Provider 文档

- [Xiaomi MiMo](docs/integrations/mimo-v2.5-pro.md)
- [Qwen Image 3.0](docs/integrations/qwen-image-3.0.md)
- [Wan3.0 Video / ComfyUI](docs/integrations/wan3-video.md)
