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

## 快速开始

> 完整安装指南请参阅 [安装文档](docs/operations/INSTALL.md)。

```powershell
# 1. 克隆并进入项目
git clone <repo-url> && cd ai_video_create

# 2. 后端安装
cd backend && python -m venv .venv
.venv\Scripts\activate && pip install -r requirements.txt

# 3. 前端安装
cd ../frontend && npm install

# 4. 配置环境变量
cd .. && Copy-Item .env.example .env
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

## 运维文档

| 文档 | 用途 |
|------|------|
| [安装指南](docs/operations/INSTALL.md) | 从零开始的完整安装步骤、配置参考、平台说明 |
| [升级指南](docs/operations/UPGRADE.md) | 版本升级流程、兼容性说明 |
| [回滚指南](docs/operations/ROLLBACK.md) | 回滚到旧版本的步骤和数据考量 |
| [问题排查](docs/operations/TROUBLESHOOTING.md) | 常见问题诊断和解决方案 |
| [安全指南](docs/operations/SECURITY.md) | 安全特性、配置建议和漏洞报告 |

## Provider 文档

- [Xiaomi MiMo](docs/integrations/mimo-v2.5-pro.md)
- [Qwen Image 3.0](docs/integrations/qwen-image-3.0.md)
- [Wan3.0 Video / ComfyUI](docs/integrations/wan3-video.md)
