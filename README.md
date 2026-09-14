# ai_video_create

本地优先、可视化的 AI 视频工作流平台。当前首个可运行切片包含：

- React Flow 可拖动画布与类型化连线
- 节点配置、自动保存、删除和画布导航
- 本地规则版 Workflow Agent，可从中文需求生成完整流程
- 提示词、结构化分镜、文生图、图生视频、合成与输出节点
- 无外部模型依赖的 Mock 顺序执行和状态反馈
- FastAPI 健康检查、工作流校验与 Agent 生成接口

## 环境

- 推荐 Node.js 18 或更高版本。当前依赖临时固定为兼容 Node 16 的 Vite 4。
- Python 3.10 或更高版本
- FFmpeg（后续真实视频合成使用）

## 安装

```powershell
npm install
npm --prefix frontend install
python -m pip install -r backend/requirements.txt
```

推荐先创建项目内虚拟环境：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

macOS/Linux 对应解释器路径为 `backend/.venv/bin/python`。根脚本会自动选择当前平台的虚拟环境解释器。

## 启动

```powershell
npm run dev
```

前端地址：`http://127.0.0.1:5173`  
API 文档：`http://127.0.0.1:8000/docs`

## 验证

```powershell
npm test
npm run typecheck
npm run build
```

完整实施路线见 `docs/plans/2026-09-14-ai-video-create-implementation-plan.md`。
