# ai_video_create 系统架构设计

> 文档职责：描述目标架构、模块边界和核心数据流
> 当前实现状态：见 [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md)
> 开发顺序：见 [`../plans/active/DELIVERY-PLAN.md`](../plans/active/DELIVERY-PLAN.md)

## 1. 架构目标

ai_video_create 是本地优先的可视化 AI 视频工作流平台。系统应在不依赖 Docker、Redis、PostgreSQL 或对象存储的情况下完成：

```text
提示词 → 结构化分镜 → 按 scene_id 生成图片 → 生成视频片段
      → FFmpeg 标准化与拼接 → 本地预览、下载与血缘追踪
```

设计原则：

1. 工作流定义与执行快照分离。
2. 后端是工作流和端口校验的最终权威。
3. Provider 适配外部协议，Handler 实现节点语义，Scheduler 负责调度。
4. 外部临时 URL 立即落地本地资产目录。
5. 长任务持久化 external job ID，重启后继续轮询，禁止重复计费提交。
6. Mock 模式完全离线并走真实调度路径。

## 2. 系统上下文

```text
┌─────────────────────────────────────────────────────────────┐
│ Browser                                                     │
│ React + TypeScript + React Flow + Zustand                   │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST + WebSocket
┌───────────────────────▼─────────────────────────────────────┐
│ FastAPI                                                     │
│ Workflow API │ Agent API │ Execution API │ Asset/Config API │
├─────────────────────────────────────────────────────────────┤
│ Domain / Engine                                             │
│ Validator │ Compiler │ Scheduler │ SQLite Queue │ WorkerPool │
├─────────────────────────────────────────────────────────────┤
│ Node Handlers                                               │
│ TextInput │ Storyboard │ T2I │ I2V │ Concat │ Output        │
├─────────────────────────────────────────────────────────────┤
│ Provider Adapters                                           │
│ MiMo │ Qwen Image │ Wan3 │ Ollama │ OpenAI │ ComfyUI │ Mock │
├─────────────────────────────────────────────────────────────┤
│ Local Services                                              │
│ SQLite │ Asset Storage │ FFmpeg │ Structured Logs           │
└─────────────────────────────────────────────────────────────┘
```

## 3. 仓库结构

```text
ai_video_create/
├── frontend/
│   ├── src/
│   │   ├── components/             画布、节点、设置、Agent、执行面板
│   │   ├── api/                    WebSocket 辅助
│   │   ├── stores/                 独立执行状态
│   │   ├── api.ts                  REST 客户端
│   │   ├── store.ts                工作流状态
│   │   └── workflow.ts             节点目录与默认流程
│   └── e2e/                        Playwright 浏览器测试
├── backend/app/
│   ├── api/                        FastAPI 路由
│   ├── db/migrations/              SQLite 迁移
│   ├── engine/                     compiler/scheduler/queue/retry/worker
│   ├── handlers/                   节点契约与执行器
│   ├── providers/                  外部模型适配器
│   ├── repositories/               Workflow/Asset 数据访问
│   └── services/                   Agent/Event/Asset/FFmpeg/Template
├── data/                            DB 与生成资产，gitignore
├── docs/                            产品、架构、计划、集成与报告
└── scripts/                         启动与发布检查
```

## 4. 前端架构

### 4.1 工作流编辑器

- `Canvas.tsx`：React Flow 画布。
- `NodePalette.tsx`：节点目录。
- `PropertyPanel.tsx`：节点配置。
- `workflow.ts`：节点类型、默认值和连线规则。
- `store.ts`：工作流、选择、历史和保存。

目标是由 Node Manifest 生成前端类型和配置表单。当前仍有手写契约，存在前后端漂移风险。

### 4.2 执行监控

- `stores/executionStore.ts`：执行生命周期、任务与节点聚合状态。
- `api/executionSocket.ts`：WebSocket、指数退避和事件补拉。
- `ExecutionPanel.tsx`：进度、事件和失败状态。

轮询是数据库事实状态的兜底，WebSocket 负责低延迟通知。客户端必须容忍重复与乱序事件。

### 4.3 Agent 与模板

- `AgentComposer.tsx` 调用 preview API，展示 warnings/diff 后确认应用。
- `TemplateSelector.tsx` 将后端返回的 WorkflowSpec 装入画布。
- 有损 GraphPatch 必须显式确认并携带 expected_version。

## 5. 后端分层

### 5.1 API 层

| 路由 | 职责 |
|---|---|
| `/api/workflows` | CRUD、复制、导入导出、乐观锁 |
| `/api/executions` | 启动、任务、事件、取消、重试、WebSocket |
| `/api/agent` | 生成/修改 preview、解释、应用 patch |
| `/api/templates` | 内置与自定义模板 |
| `/api/assets` | 资产、血缘、删除 |
| `/api/config` | Provider、设置、健康检查 |

API 错误应逐步统一为 `code/message/request_id/details` 信封。

### 5.2 编译与调度

```text
WorkflowSpec → validate → immutable ExecutionSnapshot → compile
             → Scheduler → SQLite tasks → WorkerPool
             → Handler(NodeInput) → NodeResult + ArtifactRef
```

- Compiler：拓扑、静态结构和 map 节点识别。
- Scheduler：scene item、输入组装、聚合和执行收敛。
- Queue：claim、lease、heartbeat、attempt、retry time 和条件更新。
- WorkerPool：1-8 个进程内 asyncio Worker。
- RetryPolicy：错误分类、退避和最大次数。

### 5.3 Handler 契约

```json
{
  "status": "succeeded",
  "output": {"type": "image", "value": {}},
  "artifacts": [],
  "metrics": {"duration_ms": 0},
  "error": null
}
```

Handler 返回业务错误时，Worker 必须进入 fail/retry，不得标记 completed。

## 6. Provider 边界

```text
text
  ├─ openai_compat / Xiaomi MiMo（当前默认）
  ├─ OpenAI
  ├─ Ollama
  └─ Mock

image
  ├─ DashScope Qwen Image 3.0（当前默认）
  ├─ OpenAI Images
  ├─ ComfyUI
  └─ Mock

video
  ├─ Bailian Wan3.0（当前默认，项目默认 480P）
  ├─ ComfyUI
  └─ Mock

post-processing
  └─ FFmpeg
```

详细决策见 [`adr/ADR-0001-provider-capability-boundaries.md`](adr/ADR-0001-provider-capability-boundaries.md)。

### 6.1 MiMo

- Chat Completions：`/chat/completions`。
- 支持按量与 Token Plan Base URL。
- MiMo 使用 `api-key`，没有 Bearer 前缀。
- 推理模型同时返回 reasoning/content，需要足够的 completion token 预算。

### 6.2 Qwen Image

- 原生同步 endpoint 用于常规调用。
- 异步 endpoint 用于批量任务。
- 图片临时 URL 必须立即下载。

### 6.3 Wan3

- `video-synthesis` 使用异步任务。
- `external_job_id` 持久化到 task。
- 项目默认 480P；官方 API 默认 1080P。

### 6.4 ComfyUI

- 只负责本地 `/prompt`、`/history`、`/view`。
- workflow 必须匹配实际安装的节点和模型，不能把 Wan3 云端配置塞入 ComfyUI。

## 7. 数据模型

| 表 | 用途 |
|---|---|
| `workflows` | 当前工作流和版本 |
| `executions` | 不可变快照与终态 |
| `tasks` | 队列、依赖、result、attempt、external job |
| `execution_events` | WebSocket 事件 |
| `assets` | 文件与 scene 血缘 |
| `templates` | 自定义模板 |

迁移应记录已执行版本。当前迁移器按文件执行并忽略重复列，仍需升级为正式 `schema_migrations`。

## 8. 资产与媒体

```text
data/assets/
├── images/
├── videos/
├── final/
└── temp/
```

要求：

- resolve 后路径位于 asset root。
- 临时文件 + 原子重命名。
- 记录 MIME、大小、SHA-256、execution/node/scene/provider/model/source assets。
- 被引用资产不允许删除。
- FFmpeg 合成前统一编码、尺寸、帧率、像素格式和音轨。
- FFmpeg 路径来自配置，不依赖测试进程的临时自动发现。

## 9. 配置与秘密

- 环境变量统一 `AI_VIDEO_` 前缀。
- `.env` 被 gitignore；`.env.example` 无密钥。
- Settings GET 不返回 Key。
- 设置 UI 当前只更新内存，持久配置仍以 `.env` 为准。
- 后续数据库只保存 secret reference。

## 10. 运行

```powershell
npm install
npm --prefix frontend install
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm run dev
```

- Frontend：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`
- Health：`http://127.0.0.1:8000/api/health`
- OpenAPI：`http://127.0.0.1:8000/docs`

生产前仍需解决 Node 20、本地测试依赖、FFmpeg 路径和 CI 门禁问题。

## 11. 非功能目标

| 维度 | 目标 |
|---|---|
| 启动 | 冷启动 < 5 秒，不含外部模型 |
| 并发 | 2-4 Worker，无重复 claim |
| API | 非 AI API P95 < 100ms |
| 恢复 | 无永久 pending；长任务重启可继续 |
| 安全 | 默认 127.0.0.1；密钥不进日志/导出 |
| 跨平台 | Windows/macOS/Linux Mock smoke |
| 离线 | Mock 完整链路无网络运行 |

## 12. 相关文档

- [产品需求](../product/PRD.md)
- [项目状态](../PROJECT-STATUS.md)
- [Active 交付计划](../plans/active/DELIVERY-PLAN.md)
- [MiMo](../integrations/mimo-v2.5-pro.md)
- [Qwen Image](../integrations/qwen-image-3.0.md)
- [Wan3](../integrations/wan3-video.md)
- [验收报告](../reports/)
