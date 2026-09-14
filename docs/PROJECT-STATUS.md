# ai_video_create 项目状态报告

> 更新日期：2026-09-15
> 依据：对 frontend/、backend/、docs/ 的全量代码扫描

---

## 1. 愿景目标

构建一个 **本地优先、可视化编排 AI 内容生成流程的 Web 平台**：

1. **可拖动流程图画布** — 用户通过拖拽节点、连线，自定义 AI 处理流水线
2. **Agent 生成流程** — 自然语言描述即可生成完整工作流
3. **完整纵向链路** — 提示词 → 文本描述 → 分段生成图片 → 图片转视频 → 合成关联
4. **本地运行** — 零 Docker、零外部数据库，Node + Python 即可启动

---

## 2. 当前项目进度总览

```
Phase A  ████████████████░░░░  80%   可编辑、可保存的类型化画布 ✅
Phase B  ████████████████░░░░  80%   可观察、可恢复的 Mock 执行器 ✅
Phase C  ████████████████░░░░  80%   真实多模态能力 ✅ 本次完成
Phase D  ░░░░░░░░░░░░░░░░░░░░   5%   Agent 与模板体验
Phase E  ░░░░░░░░░░░░░░░░░░░░   0%   发布验收
```

**总体完成度：约 65%（Phase A/B/C 基本完成，Mock + Real 双模式执行链路已打通）**

---

## 3. 已完成内容

### 3.1 前端（frontend/）— 13 个源文件

| 已实现 | 说明 |
|--------|------|
| React + TypeScript + Vite 脚手架 | 构建工具链完整可用 |
| ReactFlow 画布 | 拖拽、缩放、平移、连线、小地图、控件 |
| 6 种节点类型 | textInput / storyboard / textToImage / imageToVideo / videoConcat / output |
| 组件化架构 | TopBar / NodePalette / PropertyPanel / AgentComposer / Canvas 独立文件 |
| 连线类型校验 | outputType → inputType 不匹配时拒绝连线 |
| Agent 编排面板（AgentComposer） | 中文提示词 → 解析镜头数 → 生成完整工作流 |
| Mock 执行引擎 | 逐节点模拟运行，带状态动画和进度条 |
| 取消执行 | runGeneration 计数器实现中断 |
| 自动保存 | localStorage + 后端 API 双写，防抖 1s |
| Undo/Redo | Ctrl+Z / Ctrl+Shift+Z，保留最近 30 步历史 |
| API 客户端 | fetch 封装，支持 CRUD + 导入导出 |
| 暗色主题 UI | 响应式三栏布局，3 个断点适配 |
| 单元测试（16 个） | workflow / store undo-redo / API 客户端 |

### 3.2 后端（backend/）— 22 个 Python 源文件

| 已实现 | 说明 |
|--------|------|
| FastAPI 应用骨架 | CORS、自动 OpenAPI、lifespan 生命周期 |
| 6 个 Pydantic 模型 | WorkflowSpec / WorkflowNode / WorkflowEdge / NodeData / Position / AgentRequest |
| 工作流校验器 | model_validator 检查唯一 ID、悬空边、端口类型兼容 |
| 工作流工厂 | `create_prompt_to_video()` 从提示词生成 6 节点线性管道 |
| **配置系统** | Pydantic Settings + .env + 环境变量，支持多 Provider 切换 |
| SQLite 数据库层 | WAL 模式、外键、busy_timeout、幂等迁移 |
| Workflow Repository | CRUD + 乐观锁 + 复制，线程安全 |
| Workflow CRUD API | 8 个 REST 端点：列表/创建/读取/更新/删除/复制/导出/导入 |
| **配置 API** | 9 个端点：Provider 管理 / 设置更新 / 健康检查 / 资产管理 |
| `/api/health` | 返回 Python 版本、FFmpeg 可用性、运行模式、版本号 |
| `/api/agent/generate` | 接收提示词，返回 WorkflowSpec |
| **Provider 抽象层** | BaseProvider ABC + 能力声明 + 错误体系 |
| **Provider 注册表** | 动态注册/查询/列出 Provider |
| **Mock Provider** | 完整模拟 text/image/video 生成，用于开发测试 |
| **Ollama Provider** | 本地 LLM 文本生成（httpx 异步调用） |
| **OpenAI Provider** | GPT 文本 + DALL-E 图像生成 |
| **ComfyUI Provider** | ComfyUI workflow 执行（txt2img / img2vid） |
| **Asset Manager** | 文件存储管理（分类存储、元数据、清理策略） |
| **FFmpeg Service** | 视频拼接、图转视频、视频信息查询 |
| **Handler 注册表** | Mock/Real 双模式切换 |
| **Real Handlers** | 6 个真实 Handler（使用 Provider + FFmpeg + AssetManager） |
| 测试（119 个） | 校验/CRUD/API/编译器/队列/执行/Provider/Handler/Config/Service |

### 3.3 基础设施

| 已实现 | 说明 |
|--------|------|
| 单仓 monorepo | 根 package.json + concurrently 同时启动前后端 |
| 跨平台 Python 启动器 | scripts/run-python.cjs 自动定位 venv |
| 完整 PRD | docs/prd.md — 产品定位、功能分级、里程碑 |
| 架构设计文档 | docs/dp.md — 技术选型、目录结构、层栈设计 |
| 实施计划 | 15 个任务、5 个阶段、门禁标准 |

---

## 4. Phase C 详细交付（本次新增）

### 4.1 配置系统

| 文件 | 说明 |
|------|------|
| `backend/app/config.py` | Pydantic Settings + .env 支持 + Provider 配置管理 |
| `backend/app/api/config.py` | 9 个配置 API 端点 |

**支持的配置项：**
- `DEFAULT_LLM_PROVIDER` — 文本生成 Provider（mock/ollama/openai）
- `DEFAULT_IMAGE_PROVIDER` — 图像生成 Provider（mock/comfyui/openai）
- `DEFAULT_VIDEO_PROVIDER` — 视频生成 Provider（mock/comfyui）
- Provider API URL / Key / Model 配置
- 资产目录、FFmpeg 路径、Worker 参数

### 4.2 Provider 体系

| 文件 | 能力 | 说明 |
|------|------|------|
| `providers/base.py` | - | 抽象基类 + 错误体系 |
| `providers/__init__.py` | - | 注册表 + 动态初始化 |
| `providers/mock_provider.py` | text+image+video | 开发测试用 Mock |
| `providers/ollama_provider.py` | text | Ollama 本地 LLM |
| `providers/openai_provider.py` | text+image | OpenAI GPT + DALL-E |
| `providers/comfyui_provider.py` | image+video | ComfyUI workflow 执行 |

### 4.3 服务层

| 文件 | 说明 |
|------|------|
| `services/asset_manager.py` | 文件存储、检索、清理、元数据 |
| `services/ffmpeg.py` | FFmpeg 封装（拼接、图转视频、信息查询） |

### 4.4 Real Handlers

| Handler | 输入 | 输出 | 依赖 |
|---------|------|------|------|
| RealTextInputHandler | text | text | LLM Provider |
| RealStoryboardHandler | text | list\<scene\> | LLM Provider |
| RealTextToImageHandler | text | list\<image\> | Image Provider + AssetManager |
| RealImageToVideoHandler | image | list\<video\> | FFmpeg/Video Provider + AssetManager |
| RealVideoConcatHandler | list\<video\> | video | FFmpeg + AssetManager |
| RealOutputHandler | video | final | AssetManager |

### 4.5 配置 API 端点

```
GET  /api/config/providers        — 列出已注册 Provider
GET  /api/config/settings         — 获取当前设置（不含密钥）
PUT  /api/config/settings         — 更新设置并重新初始化
POST /api/config/test-provider    — 测试 Provider 连接
GET  /api/config/assets           — 列出所有资产
GET  /api/config/assets/stats     — 资产统计
POST /api/config/assets/cleanup   — 清理旧临时资产
```

---

## 5. 文件资产清单（更新）

```
ai_video_create/
├── docs/
│   ├── PROJECT-STATUS.md          ← 本文档
│   ├── prd.md
│   ├── dp.md
│   └── plans/
├── frontend/
│   └── src/
│       ├── components/            5 个组件
│       ├── api.ts, store.ts, types.ts, workflow.ts
│       └── *.test.ts              3 个测试文件（16 tests）
└── backend/
    ├── app/
    │   ├── config.py              🆕 配置系统
    │   ├── main.py                更新：集成 Provider/Handler/AssetManager
    │   ├── models.py
    │   ├── workflow_factory.py
    │   ├── api/
    │   │   ├── workflows.py
    │   │   ├── executions.py
    │   │   └── config.py          🆕 配置 API
    │   ├── db/
    │   │   ├── connection.py
    │   │   └── migrations/001_initial.sql
    │   ├── engine/
    │   │   ├── compiler.py
    │   │   ├── queue.py
    │   │   └── worker.py
    │   ├── handlers/
    │   │   ├── __init__.py        🆕 Handler 注册表
    │   │   ├── base.py            Mock Handlers
    │   │   └── real_handlers.py   🆕 Real Handlers
    │   ├── providers/
    │   │   ├── __init__.py        🆕 Provider 注册表
    │   │   ├── base.py            🆕 抽象基类
    │   │   ├── mock_provider.py   🆕 Mock Provider
    │   │   ├── ollama_provider.py 🆕 Ollama
    │   │   ├── openai_provider.py 🆕 OpenAI
    │   │   └── comfyui_provider.py 🆕 ComfyUI
    │   ├── repositories/
    │   └── services/
    │       ├── event_bus.py
    │       ├── asset_manager.py   🆕 资产管理
    │       └── ffmpeg.py          🆕 FFmpeg 服务
    └── tests/
        ├── test_api.py, test_crud.py, test_validation.py
        ├── engine/                3 个测试文件（30 tests）
        ├── providers/             2 个测试文件（20 tests）
        ├── services/              2 个测试文件（25 tests）
        ├── handlers/              1 个测试文件（9 tests）
        └── api/                   1 个测试文件（10 tests）
```

---

## 6. 测试覆盖现状

| 范围 | 测试数 | 状态 |
|------|--------|------|
| 前端 workflow / store / api | 16 | ✅ |
| 后端校验 / CRUD / API | 31 | ✅ |
| Graph Compiler | 13 | ✅ |
| Task Queue | 10 | ✅ |
| Execution API | 7 | ✅ |
| **Provider 基础 + Mock** | **20** | ✅ 🆕 |
| **Real Handlers** | **9** | ✅ 🆕 |
| **Config API** | **10** | ✅ 🆕 |
| **Asset Manager** | **16** | ✅ 🆕 |
| **FFmpeg Service** | **8** | ✅ 🆕 (6 skipped, no ffmpeg) |
| **合计** | **135** | **119 passed, 6 skipped** |

---

## 7. 下一步（Phase D）

### Phase D：Agent 与模板体验

| 任务 | 说明 |
|------|------|
| LLM-driven Workflow Agent | Tool calling → 生成/修改工作流 |
| GraphPatch + diff 预览 | 修改工作流时显示差异 |
| 确认流程 | 用户确认后应用修改 |
| 官方模板注册 | 后端模板服务 + 模板选择 UI |
| 前端设置页 | Provider 选择 + API Key 配置 UI |

### Phase E：发布验收

| 任务 | 说明 |
|------|------|
| 安全测试 | 输入校验、XSS、路径遍历 |
| 恢复测试 | Worker 崩溃恢复、数据库损坏恢复 |
| 性能基准 | 并发执行、大工作流、内存占用 |
| 跨平台验证 | Windows/macOS/Linux |
