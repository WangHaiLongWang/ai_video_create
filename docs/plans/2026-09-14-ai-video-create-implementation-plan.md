# ai_video_create 实施计划

> 日期：2026-09-14  
> 状态：待实施  
> 依据：`docs/prd.md`、`docs/dp.md` 与“通过 Agent 生成可拖动、可编辑、可执行的流程图，并完成提示词 → 文本 → 分镜 → 图片 → 视频 → 合成”的目标。

## 1. 最终目标

交付一个本地优先的 Web 平台，用户既可以拖拽编辑工作流，也可以用自然语言让 Workflow Agent 创建或修改工作流。工作流保存为有类型、可校验、可执行的 DAG；默认模板可以从一个主题生成结构化脚本与分镜，逐镜生成图片和视频，最后按顺序合成成片，并保留每个产物与上游输入的关联关系。

首版成功标准：

1. 用户输入“生成一个 5 镜头的科幻短视频流程”，Agent 返回合法工作流并显示在画布上。
2. 用户可以拖动节点、修改配置、连线、撤销、保存、刷新恢复及导入导出。
3. Mock Provider 下，默认工作流能够完整执行并产生可预览的模拟图片、视频和最终成片记录。
4. 接入真实 Provider 后，每个镜头严格保持 `scene_id` 关联：分镜文本、图片、视频一一对应，合成顺序稳定。
5. 节点状态、逐项进度、日志和错误实时显示；失败项可以重试，执行可以取消。

## 2. 对现有文档的关键修正

### 2.1 增加 Workflow Agent，而不让 Agent 直接控制运行时

Agent 是“工作流编译器”，职责是把自然语言转换为受约束的 `WorkflowSpec`，或生成针对现有图的 `GraphPatch`。它不能直接写数据库、执行任意 Python、拼接 SQL 或绕过节点注册表。

```text
自然语言
  → Agent（意图解析/选模板/补参数）
  → WorkflowSpec 或 GraphPatch（结构化 JSON）
  → Schema 校验 + 类型校验 + DAG 校验 + 安全策略
  → 用户预览差异并确认
  → 保存到画布
  → 执行引擎
```

这样可以保证 Agent 输出可解释、可撤销、可复现。Agent 生成流程与工作流执行是两条边界清晰的链路。

### 2.2 将数组映射提升为 P0

现有 PRD 把循环节点放在 P2，但核心模板需要把 `text[]` 变成 `image[]` 和 `video[]`。首版采用节点级 `map_over` 执行语义，不要求用户手工创建 N 个节点：

```text
Story[] --map--> TextToImage[] --map--> ImageToVideo[] --> VideoConcat
```

每一项都携带稳定的 `scene_id`、`index` 和上游引用。显式的通用 Loop/条件分支仍保留在 P2。

### 2.3 使用结构化分镜代替普通文本切段

核心链路不应只依靠“按字符/段落切分”。LLM 节点输出结构化 `Storyboard`：

```json
{
  "title": "...",
  "global_style": "...",
  "scenes": [
    {
      "scene_id": "scene-001",
      "index": 0,
      "narration": "...",
      "image_prompt": "...",
      "video_prompt": "...",
      "duration_seconds": 4
    }
  ]
}
```

普通 `TextSplit` 仍作为通用节点保留；默认短视频模板使用 `StoryboardGenerator` 与 `SceneMap`。

### 2.4 补齐长任务与失败传播语义

- 生图/生视频适配器统一支持 `submit → poll/progress → result → cancel`。
- 上游失败时，下游不得永久停留 pending；应转为 `blocked` 或 `skipped`。
- 重试以“执行 ID + 节点 ID + item key + attempt”标识，防止重复产物污染结果。
- Worker 重启时回收超时的 running 任务，并根据策略重试或失败。
- 视频合成前统一分辨率、帧率、编码、音轨和像素格式。

### 2.5 增加资产血缘和密钥边界

- 每个 Asset 记录 `execution_id`、`node_id`、`scene_id`、`source_asset_ids`、Provider、模型、参数、文件哈希。
- API Key 只允许环境变量或本机秘密存储引用；不得进入工作流 JSON、执行日志或导出文件。
- 静态文件接口只服务受控资产目录，所有路径必须解析并校验在该目录内。

## 3. 建议架构

```text
React + TypeScript + @xyflow/react + Zustand
        │ REST / WebSocket
FastAPI API
  ├─ Workflow CRUD / 导入导出
  ├─ Workflow Agent（tool calling + schema constrained output）
  ├─ Graph Compiler（规范化、类型检查、拓扑检查、map 展开）
  ├─ Execution Service（运行、取消、重试、恢复）
  ├─ SQLite Queue + asyncio Workers
  ├─ Provider Registry（LLM / Image / Video）
  └─ Asset Service + FFmpeg
        │
SQLite + 本地资产目录 + 可选外部模型服务
```

关键原则：

- 前后端共享一份 JSON Schema/类型定义，后端是最终校验权威。
- 工作流定义与执行快照分离。执行开始后保存不可变快照，编辑画布不影响运行中的任务。
- Provider 与节点解耦。节点声明能力，适配器完成不同服务协议转换。
- 首先用 Mock 跑通真实控制流；真实 AI 服务是可替换适配器，而不是主流程的前置条件。

## 4. 核心契约

### 4.1 端口类型

首版支持：

```text
text, storyboard, scene, image, video, asset, any
list<T>
```

连线规则：同类型可连接；`T` 不隐式变成 `list<T>`；只有声明 `map_over` 的节点可接收 `list<T>` 并逐项执行；聚合节点显式接收 `list<T>`。`any` 只允许 Output/Debug 等终端节点使用。

### 4.2 WorkflowSpec

至少包含：

```text
schema_version
id / name / description
nodes[]: id, type, position, config, inputs, execution_mode
edges[]: id, source, source_handle, target, target_handle
viewport
metadata
```

保存前依次执行：Schema 校验、节点类型存在校验、端口兼容校验、必填输入校验、环检测、Provider 能力校验和秘密字段扫描。

### 4.3 Agent 工具

Agent 首版只开放以下受限工具：

- `list_node_types()`：返回节点能力与配置 Schema。
- `list_templates()`：返回官方模板摘要。
- `get_workflow(workflow_id)`：读取当前规范化工作流。
- `validate_workflow(spec)`：返回结构、类型与 DAG 错误。
- `preview_patch(workflow_id, patch)`：返回节点/连线差异。
- `apply_patch(workflow_id, patch, expected_version)`：用户确认后乐观锁写入。

Agent 必须优先返回说明和预览；删除节点、替换 Provider、降低镜头数等有损操作必须由用户确认。

### 4.4 执行事件

WebSocket 事件采用统一信封：

```json
{
  "event_id": "...",
  "execution_id": "...",
  "node_id": "...",
  "item_key": "scene-001",
  "type": "node.progress",
  "status": "running",
  "progress": 42,
  "message": "正在生成视频",
  "timestamp": "..."
}
```

客户端重连时用 `last_event_id` 补拉事件；WebSocket 只负责通知，数据库状态是事实来源。

## 5. 实施任务

以下任务按依赖顺序排列。每个任务完成后先运行对应测试，再提交一个小而完整的变更。

### Task 1：初始化单仓与质量基线

文件：

- 新建 `package.json`
- 新建 `frontend/package.json`
- 新建 `frontend/src/main.tsx`
- 新建 `backend/pyproject.toml`
- 新建 `backend/app/main.py`
- 新建 `.env.example`、`.gitignore`、`README.md`

步骤：

1. 建立 Vite + React + TypeScript 前端和 FastAPI 后端。
2. 根脚本提供 `dev`、`test`、`lint`、`typecheck`。
3. 后端增加 `/api/health`，返回版本、数据库、FFmpeg 与资产目录状态。
4. 添加最小前后端 smoke test。

验收：全新环境按 README 启动；健康检查通过；前后端测试命令可重复运行。

### Task 2：定义共享工作流契约与节点注册表

文件：

- 新建 `schemas/workflow.schema.json`
- 新建 `schemas/node-manifest.schema.json`
- 新建 `frontend/src/types/workflow.ts`
- 新建 `frontend/src/nodes/registry.ts`
- 新建 `backend/app/domain/workflow.py`
- 新建 `backend/app/domain/node_registry.py`
- 新建 `backend/tests/domain/test_workflow_validation.py`

步骤：

1. 先写失败测试：重复 ID、悬空边、非法端口类型、缺失输入、环形图均被拒绝。
2. 定义 `WorkflowSpec`、端口类型、节点 Manifest 与版本字段。
3. 实现后端权威校验器以及前端即时校验映射。
4. 注册首批节点：TextInput、StoryboardGenerator、TextSplit、TextToImage、ImageToVideo、VideoConcat、Output。

验收：同一个 fixture 在前后端得到一致类型；非法图不能保存或运行，并返回定位到节点/边的错误。

### Task 3：SQLite 迁移与 Repository

文件：

- 新建 `backend/app/db/connection.py`
- 新建 `backend/app/db/migrations/001_initial.sql`
- 新建 `backend/app/repositories/workflows.py`
- 新建 `backend/app/repositories/executions.py`
- 新建 `backend/app/repositories/assets.py`
- 新建 `backend/tests/repositories/`

数据表：`workflows`、`workflow_versions`、`executions`、`node_runs`、`tasks`、`assets`、`execution_events`、`provider_configs`。

步骤：

1. 先写 CRUD、版本冲突、事务回滚测试。
2. 启用 WAL、foreign_keys、busy_timeout；实现顺序迁移。
3. 工作流更新使用 `version` 乐观锁。
4. Provider 配置只保存非秘密字段及环境变量引用。

验收：数据库可自动初始化；并发更新不会静默覆盖；删除工作流不会误删历史资产。

### Task 4：工作流 CRUD、导入导出与画布基础

文件：

- 新建 `backend/app/api/workflows.py`
- 新建 `frontend/src/api/workflows.ts`
- 新建 `frontend/src/stores/workflowStore.ts`
- 新建 `frontend/src/components/canvas/FlowCanvas.tsx`
- 新建 `frontend/src/components/panels/NodePalette.tsx`
- 新建 `frontend/src/components/panels/PropertyPanel.tsx`
- 新建相关前后端测试

步骤：

1. 实现工作流列表、创建、读取、更新、复制、导入和导出 API。
2. 实现节点拖入、移动、连线、删除、缩放、平移和选择。
3. 连接时实时做端口校验；错误给出可理解原因。
4. 实现至少 20 步撤销/重做；自动保存采用防抖和版本冲突提示。

验收：导出再导入结构等价；刷新恢复位置与配置；快捷键和非法连线测试通过。

### Task 5：Graph Compiler 与 map 语义

文件：

- 新建 `backend/app/engine/compiler.py`
- 新建 `backend/app/engine/graph.py`
- 新建 `backend/app/engine/context.py`
- 新建 `backend/tests/engine/test_compiler.py`
- 新建 `backend/tests/engine/test_map_execution.py`

步骤：

1. 先写拓扑排序、失败传播、稳定排序和数组映射测试。
2. 把 WorkflowSpec 编译为不可变 `ExecutionPlan`。
3. 为 map 节点按 `scene_id` 生成 item task；聚合节点按 `index` 稳定排序。
4. 检测空数组、重复 scene_id、部分失败和非法聚合。

验收：5 个 scene 生成 5 个图片任务、5 个视频任务和 1 个聚合任务；任一项的上下游关联可追踪。

### Task 6：可靠任务队列、Worker 与执行 API

文件：

- 新建 `backend/app/engine/queue.py`
- 新建 `backend/app/engine/worker.py`
- 新建 `backend/app/engine/scheduler.py`
- 新建 `backend/app/api/executions.py`
- 新建 `backend/tests/engine/test_queue.py`
- 新建 `backend/tests/api/test_executions.py`

步骤：

1. 覆盖原子领取、依赖就绪、租约超时、取消、重试、失败/跳过传播测试。
2. 实现任务租约 `lease_until` 与心跳，启动时回收孤儿任务。
3. 实现执行、取消、整次重试、单节点/单 item 重试。
4. 运行时保存工作流快照；配置修改不影响当前执行。

验收：两个 Worker 不重复领取；进程中断再启动可恢复；取消最终收敛到 cancelled；不存在永久 pending。

### Task 7：执行事件、日志和画布监控

文件：

- 新建 `backend/app/services/event_bus.py`
- 新建 `backend/app/api/ws.py`
- 新建 `frontend/src/api/executionSocket.ts`
- 新建 `frontend/src/stores/executionStore.ts`
- 新建 `frontend/src/components/panels/ExecutionPanel.tsx`
- 新建相关测试

步骤：

1. 事件先落库，再尝试推送 WebSocket。
2. 支持快照读取和按 last_event_id 补拉。
3. 节点显示 waiting/running/completed/failed/blocked/skipped/cancelled。
4. map 节点显示 `已完成/总数`、单项错误和重试入口。

验收：刷新或断线重连后状态一致；事件重复到达不会导致 UI 计数错误。

### Task 8：Handler、Mock Provider 与首条纵向链路

文件：

- 新建 `backend/app/handlers/base.py`
- 新建 `backend/app/handlers/text.py`
- 新建 `backend/app/handlers/storyboard.py`
- 新建 `backend/app/handlers/image.py`
- 新建 `backend/app/handlers/video.py`
- 新建 `backend/app/handlers/concat.py`
- 新建 `backend/app/providers/mock.py`
- 新建 `backend/tests/e2e/test_mock_video_pipeline.py`

步骤：

1. 定义 Handler 结果、进度回调、取消令牌和可重试错误类型。
2. Mock Storyboard 固定生成 N 个结构化场景。
3. Mock Image/Video 生成轻量占位产物；Mock Concat 生成最终记录。
4. 建立端到端测试：主题 → 3 scenes → 3 images → 3 videos → final output。

验收：没有 API Key、GPU 或外部网络也能验证整套调度、关联、预览与重试行为。

### Task 9：Provider 注册表与设置页

文件：

- 新建 `backend/app/providers/base.py`
- 新建 `backend/app/providers/registry.py`
- 新建 `backend/app/providers/llm/openai_compat.py`
- 新建 `backend/app/providers/llm/ollama.py`
- 新建 `backend/app/api/providers.py`
- 新建 `frontend/src/pages/ProviderSettings.tsx`
- 新建 Provider contract tests

步骤：

1. 将 Provider 按 capability 注册：`llm.chat`、`image.generate`、`video.generate`。
2. 实现健康检查、模型列表、超时、退避重试与错误归一化。
3. UI 支持新增、禁用、测试和选择 Provider；Key 输入仅写入环境变量指引/本机秘密层。
4. 用 fake HTTP server 做 contract test，不依赖真实计费接口。

验收：节点只能选择满足能力的 Provider；密钥不出现在 API 响应、日志或工作流导出中。

### Task 10：真实生图与生视频适配器

文件：

- 新建 `backend/app/providers/image/comfyui.py`
- 新建 `backend/app/providers/video/comfyui.py`
- 新建 `backend/app/providers/image/openai_compat.py`（仅在目标服务协议适用时）
- 新建 `backend/app/providers/video/http_job.py`
- 新建 `backend/tests/providers/`

步骤：

1. 为 ComfyUI 使用可配置 workflow template 和输入字段映射，不硬编码单一工作流 JSON。
2. 实现任务提交、进度轮询/WS、结果下载、取消和超时。
3. 下载前校验 MIME、大小上限和文件扩展；文件名由服务端生成。
4. Provider 响应归一为 Asset，不把外部临时 URL 当永久结果。

验收：录制响应的集成测试通过；真实服务关闭时能快速返回可操作错误，不让节点无限 running。

### Task 11：资产服务与 FFmpeg 合成

文件：

- 新建 `backend/app/services/storage.py`
- 新建 `backend/app/services/ffmpeg.py`
- 新建 `backend/app/api/assets.py`
- 新建 `frontend/src/components/assets/AssetPreview.tsx`
- 新建 `frontend/src/pages/Assets.tsx`
- 新建相关测试

步骤：

1. 资产按 execution/node/item 隔离存储，写入使用临时文件 + 原子重命名。
2. 记录哈希、大小、媒体元数据、scene_id 和 source_asset_ids。
3. FFmpeg 先 normalize，再 concat；捕获 stderr 并提供友好错误。
4. 支持预览、单个/批量下载和受控清理。

验收：不同编码的测试片段可合成；顺序与 scene.index 一致；路径穿越测试被拒绝；删除仍被执行引用的资产会被阻止。

### Task 12：Workflow Agent（生成流程）

文件：

- 新建 `backend/app/agent/system_prompt.md`
- 新建 `backend/app/agent/service.py`
- 新建 `backend/app/agent/tools.py`
- 新建 `backend/app/agent/patch.py`
- 新建 `backend/app/api/agent.py`
- 新建 `frontend/src/components/agent/AgentPanel.tsx`
- 新建 `backend/tests/agent/test_generate_workflow.py`

步骤：

1. 先写 Agent 输出非法节点、错类型连线和未知 Provider 时的修复测试。
2. 使用模型的结构化输出生成 WorkflowSpec；禁止解析自由文本中的代码并执行。
3. 生成后调用验证工具；允许限定次数的自修复，仍失败则向用户展示具体问题。
4. 前端展示新增/修改/删除 diff，用户确认后应用为单个可撤销操作。
5. 记录 Agent 会话中的模型、提示词版本、工具调用摘要，不记录秘密。

验收：至少 20 条自然语言 golden cases 中，首次或修复后生成合法图；任何 Agent 输出都无法绕过后端校验。

### Task 13：Workflow Agent（修改与解释流程）

文件：

- 修改 `backend/app/agent/service.py`
- 修改 `backend/app/agent/patch.py`
- 修改 `frontend/src/components/agent/AgentPanel.tsx`
- 新建 `backend/tests/agent/test_modify_workflow.py`

覆盖指令：增加镜头数、替换 LLM、修改画幅、在某节点后插入节点、解释失败原因、优化并行度。

验收：使用 `expected_version` 防止覆盖并发编辑；有损 patch 必须确认；应用/撤销后图结构完全可恢复。

### Task 14：官方“提示词到短视频”模板

文件：

- 新建 `templates/prompt-to-video.json`
- 新建 `backend/app/services/templates.py`
- 新建 `backend/app/api/templates.py`
- 新建 `frontend/src/components/templates/TemplateGallery.tsx`
- 新建 `backend/tests/e2e/test_prompt_to_video_template.py`

模板链路：

```text
TextInput
 → StoryboardGenerator
 → TextToImage(map scenes)
 → ImageToVideo(map images)
 → VideoConcat
 → Output
```

验收：只修改主题与镜头数即可执行；全局风格自动注入每个 image prompt；结果页能从最终视频回溯到任一 scene 的文本、图片和视频。

### Task 15：恢复性、安全与跨平台验收

文件：

- 新建 `backend/tests/security/`
- 新建 `backend/tests/recovery/`
- 新建 `scripts/check-prerequisites.*`
- 修改 `README.md`

步骤：

1. 覆盖 SSRF 基础限制、路径穿越、日志脱敏、恶意导入 JSON、超大文件和提示词注入边界。
2. 覆盖进程被终止、WebSocket 断线、Provider 超时、磁盘空间不足、FFmpeg 缺失。
3. 在 Windows、macOS、Linux 跑启动和 Mock E2E；修正路径与进程退出行为。
4. 测量冷启动、100 节点画布交互和 2-4 Worker 调度。

验收：核心恢复测试通过；Mock 模式完全离线；安装、备份、恢复、升级和故障排查文档完整。

## 6. 交付阶段与门禁

### Phase A：可编辑、可保存的类型化画布（Task 1-4）

门禁：用户可稳定创建、保存、导入导出合法 DAG。尚不接 AI 服务。

### Phase B：可观察、可恢复的 Mock 执行器（Task 5-8）

门禁：Mock 端到端链路通过，数组映射、取消、失败传播、重试、重启恢复均有自动测试。

### Phase C：真实多模态能力（Task 9-11）

门禁：至少一个真实 LLM、一个生图和一个生视频适配器通过 contract/integration test；FFmpeg 输出可播放。

### Phase D：Agent 与模板体验（Task 12-14）

门禁：自然语言可以生成和修改合法工作流，任何变更可预览、确认和撤销；默认模板一键运行。

### Phase E：发布（Task 15）

门禁：三平台 smoke test、安全与恢复测试通过，文档可供新用户独立安装。

## 7. 测试策略

- 单元测试：图校验、拓扑排序、map/aggregate、状态机、patch、路径安全。
- Contract test：每类 Provider 必须通过同一套成功、进度、超时、取消、限流和错误测试。
- 集成测试：SQLite + Worker + fake Provider + WebSocket。
- E2E：浏览器创建图、Agent 生成图、运行 Mock 模板、失败项重试、刷新恢复、下载结果。
- Golden test：自然语言 → 规范化 WorkflowSpec；只断言结构和能力，不绑定随机节点 ID 或坐标细节。
- 人工验收：拖拽手感、复杂图可读性、长任务反馈、错误文案和小屏布局。

每个缺陷先增加可复现测试，再修复；不以真实付费 API 作为 CI 必需条件。

## 8. 首版明确不做

- 多用户协作、权限/RBAC、云端部署与横向扩容。
- Agent 自主执行未确认的有损工作流修改。
- 任意 Python/JavaScript 节点及第三方插件市场。
- 通用条件分支、嵌套循环、cron、音频配音和复杂时间线编辑。
- 将所有厂商强行归为“OpenAI 兼容”；图像和视频协议按能力单独适配。

## 9. 主要风险与决策点

1. **SQLite 队列的上限**：适合本地单进程；未来多进程/多机必须替换队列层，Repository 和 Scheduler 接口需提前隔离。
2. **供应商协议差异**：视频生成往往是异步任务，不能只设计一个 `generate()` 同步接口。
3. **角色/风格一致性**：首版用 `global_style`、参考图和固定 seed 尽力保证，但不承诺跨模型绝对一致。
4. **API 成本**：运行前显示预估调用次数；批量 map 节点需要并发上限和明确确认。
5. **本地 Web 的安全面**：默认只监听 `127.0.0.1`；若用户开放局域网访问，需要额外认证与 CSRF/CORS 策略。

## 10. 推荐的第一开发切片

先完成 Task 1-2，再实现一个不落数据库的最小画布原型不是最佳主线；推荐严格完成 Task 1-4 的持久化编辑闭环，然后直接做 Task 5-8 的 Mock 纵向链路。到 Phase B 结束时，产品架构最难的部分——类型、数组映射、状态机、恢复和资产关联——已经被验证，之后接真实模型主要是适配工作。

