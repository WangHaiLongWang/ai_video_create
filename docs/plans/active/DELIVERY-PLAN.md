# ai_video_create 公司级研发交付计划

> 计划版本：1.8
> 制定日期：2026-10-10
> 校准日期：2026-10-12
> 计划状态：Active，后续开发的唯一主计划
> 当前推进计划：`docs/plans/active/PLATFORM-HARDENING-PLAN.md`（Epic H0-H6，工单以 HARD-xxx 为准）
> 状态基线：`docs/PROJECT-STATUS.md`
> 产品基线：`docs/product/PRD.md`
> 架构参考：`docs/architecture/SYSTEM-DESIGN.md`
> 历史计划：`docs/plans/archive/`

## 0. 2026-10-12 执行检查点

自 2026-10-10 状态基线（`docs/PROJECT-STATUS.md` 状态版本 19.0，代码基线 `44d2227`）以来 **无代码变更**：git 工作区干净，其后仅有文档提交。本节测试数字沿用 2026-10-10 实测，**均待同 SHA CI 复证**，不得直接作为 RC 证据。

项目主要功能模块、两轮模块化纵向开发和 Phase M3 已完成，当前重点是 Platform Hardening（Epic H0-H6）：共享契约、正式迁移、Provider 持久化、同 SHA CI、真实 Provider UAT 与 RC 发布。后续 Sprint/里程碑统一指向 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md)，本文件不再重复展开已关闭的 AVC/FE-R3/MOD-R3 旧工单。

### 已完成

| 工单/能力 | 状态 | 证据 |
|---|---|---|
| AVC-001 FastAPI 204 契约 | Done | Workflow/Asset DELETE 可导入，API 测试通过 |
| AVC-002 配置前缀 | Done | `AI_VIDEO_` env prefix |
| AVC-003 async 测试真实性 | Done | pytest-asyncio 已启用，loop scope 已固定 |
| AVC-202 Worker 结果落库 | Done | result_json 已保存，业务 error 不再 completed |
| AVC-204 execution 收敛/传播 | Done | 终态统计和递归失败传播已实现 |
| AVC-301 前端 Execution API | Done | 保存、启动、查询、取消、轮询已接入 |
| AVC-401 Asset 表/API 基础 | Done/需深化 | Migration 003、Repository 和 API 存在 |
| AVC-501 capability 独立 Provider | Done | image/video 可分别选择 DashScope/Wan3/ComfyUI |
| Qwen Image 3.0 | Done（单次 UAT） | 真实生成 1280×720 PNG |
| Wan3.0 480P Provider | Historical UAT Done/当前需复现 | 报告记录真实任务通过；当前证据待复现（RC-008） |
| Xiaomi MiMo v2.5 Pro | Done（单次 UAT） | 自定义配置、Contract、`/models` 和真实 Chat Completions 已通过 |
| AVC-201 NodeResult/ArtifactRef | Done | contracts 与 handlers 已接入 |
| AVC-203 scene map/input assembly | Done | scene mapping integration tests |
| AVC-205 取消竞态 | Done | 状态条件更新和递归取消 |
| AVC-207 WorkerPool | Done | 多 Worker tests |
| AVC-302/303 WebSocket executionStore | Done/需 E2E | 客户端与单元测试已通过，浏览器断线恢复待验收 |
| AVC-508 Wan3 external job | Done/需复现 | Migration 006、UAT 报告存在；当前证据待复现（RC-008） |

### 当前质量基线（2026-10-10 实测，待同 SHA CI 复证）

- 前端 Vitest：22 files / 387 passed；TypeScript 0 errors。
- 生产构建：index 138.51 kB；最大 chunk 185.73 kB，无 500 kB 警告。
- Playwright 全量：142 passed / 1 skipped / 0 failed（含 Modules 5/5 与 Agent Modify 3/3 真实 Mock FastAPI，零 route mock）。
- 后端干净 venv non-external：2123 passed / 8 skipped / 0 failed。
- 当前 Node 22.21.1 / Python 3.12.3；本机默认 shell 可能解析到 Node 16，Playwright 需 Node 20+（见 HARD-001）。
- 三平台 + browser-e2e CI workflow 已配置，尚无同 SHA run 证据。
- 当前综合产品完成度约 91%；功能主链成熟，进入平台硬化与 RC 证据阶段，未达到 RC。

### 当前关键路径：Platform Hardening（H0-H6）

```text
H0 可复现工具链
  → H1 共享契约单一来源
  → H2 migration ledger
  → H3 Provider 配置持久化
  → H4 Agent 兼容层收口
  → H5 同 SHA CI + 真实 Provider UAT
  → H6 RC 发布演练
```

已实现但不得误标为产品完成：

- 模块 Palette/Designer、扩展端口 Binding、effective-ports 校验、真实 Mock Backend 浏览器链、Agent Modify 增量 diff/破坏性确认均已关闭（Phase M3），但同 SHA CI 与真实 Provider UAT 证据仍缺。
- 发布阻断：RC-001/002/003 已关闭；RC-004（同 SHA CI run 证据）、RC-008（真实 Qwen/Wan3 当前证据）待办；RC-007（Doubao 模型未激活）外部阻断。
- 剩余工作是 H 系列工单（HARD-xxx）与发布证据，不是新功能。

### 剩余工作量重估（对齐 H 系列）

- 两人并行约 7-10 个工作日；单人约 12-16 个工作日（外部模型激活等待不计入工程工期）。
- 最大不确定性：共享契约收敛、migration ledger 旧库升级与中断恢复、同 SHA CI 证据、真实 Provider UAT。

## 1. 计划目标

将当前“模块较多但主链未贯通”的原型，交付为一个可安装、可恢复、可验证的本地 AI 视频工作流产品。首个正式版本必须完成下面的用户闭环：

```text
创建/Agent 生成工作流
  → 编辑并保存
  → 校验和编译 DAG
  → 执行结构化分镜
  → 按 scene_id 生成图片
  → 按 scene_id 生成视频
  → FFmpeg 合成
  → 预览/下载
  → 查看历史、失败项重试和资产血缘
```

计划以端到端用户价值为完成标准。以下情况不计为完成：只有类或接口、只有 Mock 单元测试、组件没有挂载、API 没有前端消费者、错误被降级为不存在的成功文件、异步测试被跳过。

## 2. 交付范围

### 2.1 v1.0 必须交付

- React Flow 工作流编辑器：拖入、连线、配置、撤销/重做、保存、导入/导出。
- 类型化节点契约与后端权威校验。
- SQLite 工作流、执行、任务、事件、资产和配置持久化。
- 可恢复 DAG 执行器：结果传递、map/aggregate、失败传播、取消、重试、2-4 Worker。
- Mock 完整链路，完全离线可运行。
- Qwen Image 3.0 生图、Wan3.0 480P 生视频和 FFmpeg 合成；ComfyUI 保留为本地可选 Provider。
- 后端 Workflow Agent：生成、修改、解释、校验、diff 确认。
- 模板、Provider 设置、执行历史、资产预览与下载 UI。
- Windows/macOS/Linux 启动 smoke test，安全和恢复门禁。

### 2.2 v1.0 不做

- 多用户、RBAC、实时协作、云端横向扩容。
- 任意 Python/JavaScript 自定义执行节点。
- 插件市场、cron、通用条件分支、嵌套循环。
- 专业时间线编辑、配音、字幕和音频混音。
- 为每个云厂商实现专用 Provider；首版只建立可扩展契约并验证代表性适配器。

## 3. 团队、节奏和工期

### 3.1 估算基线

建议最小团队：

| 角色 | 投入 | 责任 |
|---|---:|---|
| Tech Lead/Backend | 1 FTE | 契约、数据库、执行器、Provider、代码评审 |
| Frontend Engineer | 1 FTE | 画布、执行监控、Agent/模板/资产 UI、浏览器测试 |
| QA/Automation | 0.5 FTE | 测试计划、E2E、跨平台、回归与发布验收 |
| Product Owner | 0.2 FTE | 验收口径、优先级、供应商选择和 UAT |
| Designer | 0.1-0.2 FTE | 核心状态、空态、错误态和交互走查 |

计划总工作量约 **75-90 人日**，含评审、测试、修复和 15% 风险缓冲：

- 上述团队：预计 10-12 周。
- 单人全栈：预计 18-22 周，且跨平台与真实 Provider 验证需额外协助。
- 工期不包含外部 API 审批、百炼 Workspace 开通、GPU/ComfyUI 环境搭建和模型下载等待。

### 3.2 研发节奏

- Sprint 长度：2 周。
- Sprint Planning：每两周首日，确认容量、依赖和验收人。
- Daily：15 分钟，只同步阻断和接口变化。
- Refinement：每周一次，下一 Sprint 条目必须达到 Definition of Ready。
- Demo/UAT：每个 Sprint 末，必须演示真实可运行链路，不接受仅展示代码。
- Retrospective：记录流程问题和行动项，行动项进入下一 Sprint。
- Release：主分支始终可构建；里程碑使用 `v0.x.0`，正式版本使用 `v1.0.0`。

## 4. 工程治理

### 4.1 分支与提交

- 主分支：`main`，禁止直接提交。
- 分支：`feat/AVC-123-short-name`、`fix/AVC-123-short-name`。
- 一个 PR 对应一个可验收工单；数据库迁移可与直接消费者放在同一 PR。
- Conventional Commits；PR 描述必须包含范围、风险、测试证据、迁移和回滚说明。
- 至少一名工程师批准；执行器、数据库、安全、Provider 变更需要 Tech Lead 批准。

### 4.2 Definition of Ready

工单进入 Sprint 前必须具备：

- 用户价值和不做范围明确。
- API/数据契约或 UI 状态已经确认。
- 前置依赖已完成或同 Sprint 有明确顺序。
- 验收标准可自动或人工验证。
- 已标注安全、数据迁移、跨平台和外部服务影响。
- 工作量不超过 3 人日；超过则继续拆分。

### 4.3 Definition of Done

工单完成必须同时满足：

- 生产代码与错误路径完成，无静默 Mock 成功降级。
- 单元/集成测试新增并通过；修复缺陷先有回归测试。
- 类型检查、lint、前后端完整测试和生产构建通过。
- API/OpenAPI、迁移、配置样例和用户文档同步更新。
- 日志不含密钥和完整用户敏感输入。
- UI 具备 loading/empty/error/disabled/retry 状态和键盘可访问性。
- PR 已评审，验收证据附在工单，必要时完成 UAT。
- 功能可以回滚，迁移有向前恢复方案。

### 4.4 CI 门禁

每个 PR 独立执行，任何一项失败即失败：

```text
frontend-unit     npm --prefix frontend test
frontend-types    npm --prefix frontend run typecheck
frontend-build    npm --prefix frontend run build
backend-unit      python -m pytest backend/tests/unit backend/tests/engine ...
backend-api       python -m pytest backend/tests/api
backend-e2e       python -m pytest backend/tests/acceptance
security          python -m pytest backend/tests/security
```

补充门禁：

- pytest 不允许 unknown mark 或 unhandled coroutine warning。
- 非明确标记为 `external` 的测试不允许 skip。
- 覆盖率初始门槛：后端 75%、前端 65%；核心 compiler/queue/scheduler/patch 目标 90%。
- 依赖漏洞 high/critical 为 0；构建产物和许可证清单归档。
- main 每晚执行 Windows/macOS/Linux smoke matrix。

## 5. 目标架构与边界

### 5.1 单一事实来源

新增 `schemas/`，Node Manifest 和 Workflow Schema 是类型、校验、前端表单与 Agent 工具描述的单一来源。

```text
schemas/node-manifest.schema.json
schemas/workflow.schema.json
schemas/execution-event.schema.json
            │
            ├─ 生成 frontend/src/generated/*
            └─ 后端 Pydantic 校验/Node Registry
```

禁止继续在 `frontend/workflow.ts`、`backend/models.py`、`services/agent.py` 中分别维护不一致的节点类型。

### 5.2 执行边界

```text
WorkflowSpec（可编辑）
  → validate
  → ExecutionSnapshot（不可变）
  → ExecutionPlan
  → Scheduler/Queue
  → Handler(NodeInput, RunContext)
  → NodeResult
  → Task/NodeRun/Asset 持久化
  → 下游 NodeInput
```

Worker 只负责租约和运行 Handler；Scheduler 负责依赖、输入组装、map/aggregate 和 execution 终态；Handler 不直接修改任务状态。

### 5.3 核心结果契约

```json
{
  "status": "succeeded",
  "output": {
    "type": "image",
    "value": {"asset_id": "asset-...", "scene_id": "scene-001"}
  },
  "artifacts": ["asset-..."],
  "metrics": {"duration_ms": 1234},
  "error": null
}
```

错误结果必须包含 `code`、`message`、`retryable` 和经过脱敏的 `details`。Handler 返回 error 时不得把 task 标为 completed。

### 5.4 map/aggregate 语义

- storyboard 输出实际 `list<scene>` 后才创建/激活 scene item。
- item key 使用稳定 `scene_id`，index 只用于展示和最终排序。
- `textToImage(scene-001)` 只依赖对应 scene；`imageToVideo(scene-001)` 只依赖对应 image。
- VideoConcat 接收按 scene.index 排序的 `list<video>`。
- 空列表合法性由节点 Manifest 声明，默认阻止合成空视频。
- 部分失败策略首版只支持 `fail_fast` 和 `all_or_nothing`，不默认生成缺镜头成片。

## 6. 数据库演进计划

不得修改已发布迁移。新增迁移文件并记录 `schema_migrations`。

### Migration 002：执行结果与重试

文件：`backend/app/db/migrations/002_execution_results.sql`

- tasks 增加 `result_json`、`attempt_count`、`max_attempts`、`next_retry_at`、`heartbeat_at`。
- executions 增加 `error_summary`、`updated_at`。
- 新增 `node_runs`，记录每次 task attempt、输入快照、结果、错误和耗时。
- 为 `(execution_id, status, next_retry_at)` 建索引。

### Migration 003：资产血缘

文件：`backend/app/db/migrations/003_assets.sql`

- 新增 `assets`：id、execution_id、node_id、scene_id、kind、relative_path、mime、size、sha256、provider、model、params_json、metadata_json、created_at。
- 新增 `asset_sources(asset_id, source_asset_id)`。
- 删除文件前检查引用；数据库事务成功后才进入可清理队列。

### Migration 004：Provider 与模板持久化

文件：`backend/app/db/migrations/004_provider_templates.sql`

- 新增 `provider_configs`，只存非秘密配置和 secret reference。
- 新增 `workflow_templates` 和版本字段。
- API Key 只使用环境变量引用或后续操作系统秘密存储，不写 graph、DB 普通字段和导出 JSON。

### 迁移策略

- 每次启动先备份 DB 元数据并在单事务内执行下一版本。
- SQLite 不支持安全回滚的结构变更采用向前修复迁移，不自动降级 schema。
- 发布回滚时旧二进制只能读取兼容 schema；不兼容变更必须先提供双读阶段。
- 测试覆盖空库、v1 库升级、重复执行、迁移中断和损坏备份恢复。

## 7. Epic 与研发工单

估算单位为理想人日，不含 15% 总体缓冲。P0 是发布阻断，P1 是 v1 必须，P2 可在容量不足时延后。

### Epic E0：可信开发基线

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-001 | P0 | 0.5 | 修复 FastAPI DELETE 204 导入错误 | `api/workflows.py`, API tests | 无 |
| AVC-002 | P0 | 0.5 | 配置统一 `AI_VIDEO_` 前缀，消除 DEBUG/HOST 污染 | `config.py`, `.env.example` | 无 |
| AVC-003 | P0 | 0.5 | 固定 pytest async 配置与依赖，禁止假 skip | `requirements.txt`, `pyproject.toml` | 无 |
| AVC-004 | P0 | 1.0 | 建立独立 CI jobs 和三平台 nightly skeleton | `.github/workflows/*` | 001-003 |
| AVC-005 | P1 | 0.5 | README、启动检查和版本要求校正 | `README.md`, `scripts/*` | 001-003 |

验收：App 可导入和启动；完整后端测试可收集；前端 test/typecheck/build 与后端 pytest 都独立通过。

### Epic E1：统一契约与数据模型

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-101 | P0 | 2.0 | Node Manifest、端口和 Workflow JSON Schema | `schemas/*`, `domain/node_registry.py` | E0 |
| AVC-102 | P0 | 1.5 | 后端权威图校验：节点、端口、必填输入、环、秘密 | `domain/workflow.py`, `models.py` | 101 |
| AVC-103 | P1 | 1.5 | 从 Schema 生成/映射前端类型和配置表单描述 | `frontend/src/generated/*`, `workflow.ts` | 101 |
| AVC-104 | P0 | 1.5 | 顺序迁移运行器和 schema_migrations | `db/connection.py`, `db/migrations/*` | E0 |
| AVC-105 | P0 | 2.0 | Migration 002 + Execution/Task/NodeRun Repository | `db/migrations/002*`, `repositories/*` | 104 |

验收：同一 fixture 前后端类型一致；非法图不能创建、更新或执行；v1 数据库可无损升级并重复启动。

### Epic E2：可靠执行器

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-201 | P0 | 1.5 | `NodeInput/NodeResult/NodeError` 契约 | `handlers/contracts.py` | E1 |
| AVC-202 | P0 | 2.0 | Worker 保存结果并正确识别业务错误 | `engine/worker.py`, `engine/queue.py` | 105,201 |
| AVC-203 | P0 | 3.0 | Scheduler 组装上游结果和 scene map/aggregate | `engine/scheduler.py`, `compiler.py` | 202 |
| AVC-204 | P0 | 1.5 | execution 终态和递归失败/blocked/skipped 传播 | `engine/scheduler.py`, `repositories/executions.py` | 203 |
| AVC-205 | P0 | 2.0 | CancellationToken 和取消竞态防护 | `engine/worker.py`, `api/executions.py` | 202 |
| AVC-206 | P0 | 2.0 | retry/attempt/退避/单 item 重试/幂等键 | `engine/queue.py`, `api/executions.py` | 202,204 |
| AVC-207 | P1 | 1.5 | 配置化 2-4 Worker 和原子 claim 并发测试 | `main.py`, `engine/queue.py` | 202 |
| AVC-208 | P0 | 2.0 | Mock 全链集成测试和崩溃恢复测试 | `tests/acceptance/*`, `tests/recovery/*` | 203-207 |

验收：3 scenes 精确形成 3 image、3 video 和 1 concat 输入；成功、失败、取消、重试和重启均收敛，无永久 pending。

### Epic E3：前端执行闭环

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-301 | P0 | 1.5 | execution REST client 和响应类型 | `frontend/src/api/executions.ts` | E2 API |
| AVC-302 | P0 | 2.0 | WebSocket 客户端、重连和 last_event_id 补拉 | `frontend/src/api/executionSocket.ts` | 301 |
| AVC-303 | P0 | 2.0 | executionStore、节点/item 状态归并和持久恢复 | `frontend/src/stores/executionStore.ts` | 301,302 |
| AVC-304 | P0 | 1.5 | 运行按钮改为保存后启动真实后端执行 | `TopBar.tsx`, `store.ts` | 303 |
| AVC-305 | P1 | 2.0 | ExecutionPanel、map 进度、错误和重试 UI | `components/ExecutionPanel.tsx` | 303,E2 |
| AVC-306 | P1 | 1.5 | 工作流列表、保存状态、冲突处理、导入导出 UI | `components/WorkflowMenu.tsx`, `store.ts` | E1 |
| AVC-307 | P1 | 1.5 | 侧栏 HTML DnD 和历史事务化 | `NodePalette.tsx`, `Canvas.tsx`, `store.ts` | 无 |
| AVC-308 | P0 | 2.0 | Playwright Mock 浏览器 E2E | `frontend/e2e/*` | 304-307 |

验收：浏览器内从主题输入到 final Mock 资产成功；刷新后状态恢复；后端失败在节点上可见且可单项重试。

### Epic E4：资产与媒体处理

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-401 | P0 | 2.0 | Migration 003 和 Asset Repository | `003_assets.sql`, `repositories/assets.py` | E1 |
| AVC-402 | P0 | 2.0 | 路径根边界、原子写、哈希、MIME/大小校验 | `services/asset_manager.py` | 401 |
| AVC-403 | P0 | 2.5 | FFmpeg normalize + concat + ffprobe 验证 | `services/ffmpeg.py` | 402 |
| AVC-404 | P1 | 1.5 | Asset API：列表、详情、下载、受控删除 | `api/assets.py` | 401,402 |
| AVC-405 | P1 | 2.0 | 节点预览、资产页面和血缘导航 | `frontend/src/components/assets/*` | 404,E3 |
| AVC-406 | P0 | 1.5 | 本机 FFmpeg 真实小视频集成测试 | `tests/integration/test_ffmpeg_pipeline.py` | 403 |

验收：最终 MP4 可由 ffprobe 读取和播放器播放；每项资产可以回溯 execution、node、scene 和 source assets。

### Epic E5：真实 Provider

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-501 | P0 | 2.0 | 按 capability 选择 Provider，取消全局 Mock/Real Handler 开关 | `providers/__init__.py`, `handlers/*` | E2 |
| AVC-502 | P0 | 2.0 | JobHandle submit/poll/progress/cancel 契约 | `providers/base.py` | 501 |
| AVC-503 | P1 | 2.0 | Ollama contract tests 和错误归一化 | `ollama_provider.py`, provider tests | 502 |
| AVC-504 | P1 | 2.5 | ComfyUI workflow template 映射和 contract tests | `comfyui_provider.py`, `config/comfyui/*` | 502 |
| AVC-505 | P1 | 2.0 | OpenAI text/image contract tests、429 和超时 | `openai_provider.py`, provider tests | 502 |
| AVC-506 | P0 | 2.0 | 真实 Handler 使用 NodeInput/AssetRef，不允许假成功 fallback | `real_handlers.py` | 401,501-505 |
| AVC-507 | P0 | 2.0 | 一条真实纵向链路 UAT | `tests/integration/*`, UAT checklist | 506,E4 |
| AVC-508 | P1 | 2.5 | Wan3.0 480P 视频 JobHandle、task_id 持久化和 contract tests | `wan3_provider.py`, node_runs | 502,105 |

验收：不同能力可混合选择；外部服务失败有明确可重试错误；至少一条真实链路生成可播放视频。

### Epic E6：Agent、模板和设置产品化

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 依赖 |
|---|---|---:|---|---|---|
| AVC-601 | P0 | 2.0 | Agent tools：节点目录、模板、校验、patch preview | `services/agent_tools.py` | E1 |
| AVC-602 | P0 | 2.5 | 结构化 WorkflowSpec/GraphPatch 输出和有限自修复 | `services/agent.py` | 601,E5 LLM |
| AVC-603 | P0 | 1.5 | generate/modify 预览与 expected_version apply | `api/agent.py`, `models.py` | 602 |
| AVC-604 | P1 | 1.5 | Migration 004、模板和 Provider 配置持久化 | `004_provider_templates.sql`, repositories | E1 |
| AVC-605 | P0 | 2.5 | AgentComposer 调用后端、diff、确认、撤销、解释 | `AgentComposer.tsx`, `api/agent.ts` | 603,E3 |
| AVC-606 | P1 | 2.0 | SettingsPanel 挂载、统一样式和秘密引用 UX | `SettingsPanel.tsx`, `TopBar.tsx` | 604 |
| AVC-607 | P1 | 1.5 | TemplateSelector 挂载并把 response spec 装入画布 | `TemplateSelector.tsx`, `TopBar.tsx` | 604 |
| AVC-608 | P0 | 2.0 | 20+ 中文 golden cases 与有损操作测试 | `tests/agent/golden/*` | 602-607 |

验收：自然语言生成/修改流程可预览、确认、撤销；非法图无法应用；重启后模板和非秘密设置仍存在。

### Epic E7：安全与发布 — ✅ 安全加固完成

| ID | 优先级 | 工作量 | 交付内容 | 主要文件 | 状态 |
|---|---|---:|---|---|---|
| AVC-701 | P0 | 2.0 | 注册安全中间件、流式 body limit、CORS/headers | `main.py`, `middleware.py` | ✅ 完成 |
| AVC-702 | P0 | 2.0 | SSRF、重定向、URL allow policy 和下载限制 | `middleware/ssrf.py` | ✅ 完成 |
| AVC-703 | P0 | 1.5 | 密钥/日志/导出脱敏测试 | `tests/security/*` | ✅ 完成 |
| AVC-704 | P0 | 2.0 | DB 备份恢复、磁盘满、资产丢失和 Worker 崩溃演练 | `scripts/backup*`, recovery tests | ⏳ P2 |
| AVC-705 | P0 | 2.0 | Windows/macOS/Linux release smoke matrix | CI workflows | ✅ 已配置 |
| AVC-706 | P1 | 1.5 | 性能与资源基准，形成可重复报告 | performance tests, `docs/benchmarks.md` | ⏳ P2 |
| AVC-707 | P0 | 2.0 | 安装、升级、回滚、故障排查和发布说明 | `README.md`, `docs/operations/*` | ⏳ RC Sprint |

E7 安全加固完成清单：
- ✅ Rate Limiting（滑动窗口，60/min default，20/min for /api/agent/*）
- ✅ SSRF Protection（IP 黑名单验证，loopback/私有/链路本地）
- ✅ CORS Refinement（动态配置，env var → dev defaults → empty）
- ✅ Security Headers（8 项安全头，CSP/HSTS/X-Frame-Options 等）
- ✅ Audit Logger（结构化 JSON 审计日志，logs/audit.jsonl）
- ✅ Secrets Scanner（7 类密钥模式检测 + CI 集成）
- ✅ Encrypted Secret Storage（AES-256-GCM 加密 + 密钥轮换）
- ✅ 三平台 CI（ci.yml + security-scan.yml 已配置）

验收：Release Checklist 全绿；三平台 Mock smoke 通过；安全/恢复演练有证据；新用户能按文档安装和恢复。

## 8. Sprint 与里程碑安排

### 已完成 Sprint F0-F4：产品能力开发（功能完成，门禁按 RC/H 系列收口）

Sprint F0-F4 已全部完成：
- ✅ F0：恢复基础门禁 — 前端基础测试全绿（当时 295 tests）
- ✅ F1：React Flow 人工编辑闭环 — 连线/拖拽/EdgeInspector/undo-redo
- ✅ F2：字段与端口产品化 — CRUD/Edge 级联/WorkflowSpec 2.0 roundtrip
- ✅ F3：Workflow Agent v2 前端闭环 — v2 API adapter + 37 golden case
- ✅ F4：Scene/安全加固 — E7 7/7 项完成 + SKI-009 预览/重试

### 当前 Sprint 阵列：Platform Hardening（见 PLATFORM-HARDENING-PLAN）

范围：Epic H0-H6，工单明细、工作量和验收以 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md) 为准，本文件不重复展开。

| Sprint | 范围 | 出口 |
|---|---|---|
| H1（3-4 天） | H0 工具链 + H1 共享契约 + H2 migration ledger | Node/Python 一致、Schema 单一来源、旧库无损升级 |
| H2（3-4 天） | H3 Provider 持久化 + H4 Agent 兼容层 | 设置重启恢复、Key 不回显、Agent v2 冻结 |
| H3（2-3 天） | H5 CI/UAT + H6 发布演练 | 同 SHA required checks、最小真实 UAT、可回滚发布 |

RC 门禁现状（2026-10-12，与 `PROJECT-STATUS.md` §6 一致）：

1. ✅ RC-001 干净环境依赖证据（干净 venv non-external 通过）
2. ✅ RC-002 模块真实 Backend 浏览器链路（Modules 5/5 零 route mock）
3. ✅ RC-003 Vitest 资源/隔离治理（连续两次与串行全绿）
4. ⏳ RC-004 同一 commit CI 证据 → HARD-501/502
5. ⏳ RC-008 真实 Qwen/Wan3 当前证据 → HARD-503/504
6. ⏳ RC-007 Doubao 模型激活（外部阻断）→ HARD-505

Demo：按 HARD 工单验收；H3 出口对齐 PLATFORM-HARDENING-PLAN §11 Definition of Done。

里程碑：`v1.0.0-rc.1`（tag 只指向已验证 SHA），验收通过后发布 `v1.0.0`。

### 已完成：React Flow 交互修复（2026-09-16）

范围：CANVAS-001 至 CANVAS-003。

1. ✅ 修复 `.canvas-shell` CSS，添加 `height: 100%` 和 `overflow: hidden` 确保 React Flow 正确填充。
2. ✅ Canvas 组件添加显式 `panOnDrag`、`nodesDraggable`、`nodesConnectable`、`selectNodesOnDrag={false}`。
3. ✅ NodePalette 添加 HTML5 Drag and Drop 支持 — 节点可从侧栏拖拽到画布。
4. ✅ Canvas 添加 `onDragOver`/`onDrop` 处理器，使用 `screenToFlowPosition` 计算放置坐标。
5. ✅ 修复 jsdom 30 + undici 8 与 Node 26 不兼容问题，切换到 happy-dom。
6. ✅ vitest.config.ts 使用 `environmentMatchGlobs` 按文件类型选择环境。

里程碑：画布可平移、节点可拖拽、可从侧栏拖入节点。

### 已完成：连线恢复与 Workflow Agent 2.0

计划：[`REACT-FLOW-AGENT-PLAN.md`](REACT-FLOW-AGENT-PLAN.md)

该专项的主要功能已完成，后续只保留共享契约（H1）、Agent v1/v2 兼容策略（H4）和 E2E/CI 收口（H5），不再重复排期 Handle、PortEditor 或 Agent adapter 的开发。

### 已完成：React Flow 与 Scene Prompt 产品化（功能已实现）

专项计划：[`FRONTEND-FLOW-SCENE-PLAN.md`](FRONTEND-FLOW-SCENE-PLAN.md)

1. F1 端口图契约、连接校验和 WorkflowSpec 2.0 已实现。
2. F2 Scene Bundle、Draft/lock、Scene Editor、导入导出已实现。
3. F3 Provider Prompt、画布交互和浏览器 E2E 已实现，真实 Mock Backend 联调已在 Phase M3 关闭。

Demo：用户连接多端口节点，编辑每个 scene，并导出可重新导入的 Prompt Bundle 与 Provider 请求预览。

里程碑：功能里程碑已完成，版本发布依赖 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md) 的 H5/H6 与 RC 门禁。

### 首条真实验收工作流：冬季滑雪教学

执行计划：[`SKI-LESSON-WORKFLOW-PLAN.md`](SKI-LESSON-WORKFLOW-PLAN.md)

该工作流作为 Flow/Scene 专项的纵向验收：一个 Scene 生成两个图片变体，每张图片生成 3 秒 Wan3 视频，再由 FFmpeg 合成为约 6 秒视频。所需 `variantCount`、scene+variant 血缘和 aggregate 顺序必须实现为通用可插拔能力。

### 发布收敛（原 Release Candidate Sprint，已并入 H 系列）

原 RC Sprint 中的 E7 安全、三平台 CI 配置、SKI-009 预览/重试、Playwright 失败修复与干净 venv 证据均已完成（见 §0 与 `PROJECT-STATUS.md`）。剩余发布工作不再单列 Sprint，全部纳入 Sprint H3（H5 CI/UAT + H6 发布演练），见 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md)。

## 9. API 交付契约

保持当前 URL 兼容，新增接口时先更新 OpenAPI 和前端类型。

### 9.1 Workflow

- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/workflows/{id}`
- `PUT /api/workflows/{id}`，请求必须是 `WorkflowSpec + expected_version`，不接受裸 dict。
- `DELETE /api/workflows/{id}`，204 且严格空响应。
- `POST /api/workflows/import` 和 `GET /api/workflows/{id}/export`。

### 9.2 Execution

- `POST /api/executions/{workflow_id}/start`，支持 `Idempotency-Key`。
- `GET /api/executions/{id}`，包含 status、task_summary、timestamps、error_summary。
- `GET /api/executions?workflow_id=&cursor=`，执行历史分页。
- `GET /api/executions/{id}/tasks`。
- `POST /api/executions/{id}/cancel`。
- `POST /api/executions/{id}/retry`，请求包含 node_id/item_key/expected_attempt。
- `WS /api/executions/{id}/ws`，事件包含单调 sequence；重连按 sequence 补拉，不只依赖时间戳。

### 9.3 Asset

- `GET /api/assets?execution_id=&kind=&cursor=`。
- `GET /api/assets/{id}`。
- `GET /api/assets/{id}/content`，正确 Content-Type、Content-Length 和下载名。
- `DELETE /api/assets/{id}`，被引用时返回 409。

### 9.4 Agent

- `POST /api/agent/generate-preview`，不写库。
- `POST /api/agent/modify-preview`，返回 GraphPatch、diff、warnings、destructive。
- `POST /api/agent/apply-patch`，必须带 expected_version。
- `POST /api/agent/explain`。

所有错误统一：

```json
{
  "error": {
    "code": "WORKFLOW_VERSION_CONFLICT",
    "message": "工作流已被更新，请刷新后重试",
    "request_id": "req-...",
    "details": {}
  }
}
```

## 10. 测试与验收策略

### 10.1 测试分层

| 层级 | 目的 | 外部依赖 | 运行频率 |
|---|---|---|---|
| Unit | 状态机、校验、映射、patch、路径策略 | 无 | 每次 PR |
| Contract | Provider 协议和错误归一化 | fake HTTP/WS server | 每次 PR |
| Integration | SQLite、Worker、Scheduler、Asset、FFmpeg | 临时目录；FFmpeg job 可选 | 每次 PR/夜间 |
| API | FastAPI 生命周期和响应契约 | 临时 DB | 每次 PR |
| Browser E2E | 用户真实操作和断线恢复 | Mock backend | 每次 PR 核心集 |
| External smoke | Qwen Image/Wan3/Ollama/ComfyUI/OpenAI | 真实服务/密钥 | 手工或 nightly 可选 |
| UAT | 内容创作者完成真实用例 | 真实环境 | 每个里程碑 |

### 10.2 v1.0 必测场景

1. 主题生成 1、3、20 镜头；scene_id 与顺序稳定。
2. 中间某张图失败，后续状态收敛且只重试该 item。
3. 生成视频期间取消，返回后不能覆盖 cancelled。
4. Worker 运行中进程退出，租约到期后恢复且不重复资产。
5. WebSocket 断开并刷新，补拉后 UI 与数据库一致。
6. 两标签同时修改工作流，旧版本 apply 返回 409。
7. 非法图、环、未知节点、错误端口和秘密字段被拒绝。
8. 外部 Provider 超时、429、坏响应、断线和取消。
9. 路径穿越、恶意文件名、超大下载、SSRF 和重定向。
10. 不同分辨率/帧率片段合成，最终文件可播放。
11. 数据库从每个历史 schema 升级，失败后可恢复备份。
12. 完全断网时 Mock 模式可完整运行。

## 11. 环境、配置与发布

### 11.1 环境

| 环境 | 用途 | 数据 |
|---|---|---|
| Local | 日常开发 | 独立 `data/dev`，Mock 默认 |
| CI | 自动测试 | 临时 DB/目录，用后删除 |
| Integration | Qwen Image/Wan3/Ollama/ComfyUI/FFmpeg 集成 | 专用测试模型和资产 |
| UAT | 产品验收 | 代表性真实工作流，不复用生产密钥 |
| Release | 用户本地安装包/源码 | 首次启动初始化 |

配置全部使用 `AI_VIDEO_` 前缀。仓库提交 `.env.example`，不提交 `.env`、密钥、真实用户素材和生成资产。

### 11.2 可观测性

- 每个 HTTP 请求生成 request_id。
- 日志字段：execution_id、task_id、node_id、scene_id、provider、attempt、duration_ms、error_code。
- 不记录 API Key、Authorization、完整 Provider 响应和二进制内容。
- 本地首版使用结构化 JSON 日志和滚动文件，无需引入外部监控服务。
- 健康检查区分 liveness/readiness，并报告 DB、FFmpeg 和已配置 Provider，不调用计费生成接口。

### 11.3 发布与回滚

发布前：

1. 代码冻结并生成 RC。
2. 运行完整 CI、三平台 smoke、迁移演练、依赖扫描和 UAT。
3. 备份测试数据库并验证恢复。
4. 生成 changelog、已知问题、配置迁移和回滚说明。

发布策略：先内部内容团队试用 3-5 天，再发布 v1.0。默认启用 Mock，真实 Provider 由用户显式配置。

回滚策略：保留上一版本二进制/源码和数据库备份。代码可回滚，数据库优先向前修复；生成资产不自动删除。任何自动清理功能发布初期使用 dry-run 默认值。

## 12. 风险登记

| ID | 风险 | 概率/影响 | 应对 | Owner | 触发条件 |
|---|---|---|---|---|---|
| R1 | 执行结果契约继续漂移 | 高/高 | Sprint 1 冻结 NodeResult，Schema 单一来源 | Tech Lead | 前后端出现不同字段名 |
| R2 | SQLite 多 Worker 锁竞争 | 中/高 | 原子 claim、短事务、WAL、压力测试 | Backend | busy/锁超时超过阈值 |
| R3 | 视频 API 长任务协议差异 | 高/高 | JobHandle 适配层，不把轮询写入 Handler | Backend | 新 Provider 无法映射 |
| R4 | 资产增长耗尽磁盘 | 中/高 | 配额、预估、清理 dry-run、空间预检 | Backend/QA | 剩余空间低于阈值 |
| R5 | Agent 生成非法或有损图 | 高/高 | 结构化输出、后端校验、diff、确认 | Tech Lead | 校验失败率超过 5% |
| R6 | 角色/画风跨镜头不一致 | 高/中 | global style、参考图、seed、清晰产品提示 | Product | UAT 一致性不可接受 |
| R7 | 外部 API 成本失控 | 中/高 | 运行前调用量估算、并发/镜头上限 | Product | 单次成本超过预算 |
| R8 | 三平台 FFmpeg 行为差异 | 中/高 | 固定支持版本、matrix smoke、明确安装检查 | QA | 任一平台输出不可播放 |
| R9 | 单人开发导致关键知识集中 | 中/中 | ADR、PR 评审、运行手册、结对关键模块 | Lead | 关键模块只有一人理解 |

## 13. 质量和产品指标

v1.0 发布目标：

- Mock 标准流程成功率 100%。
- 真实链路在已验证配置下成功率 ≥ 95%（排除供应商明确故障）。
- 100 节点工作流编译 P95 < 100 ms。
- 非 AI API 本地 P95 < 100 ms。
- WebSocket 重连后 2 秒内状态一致。
- 取消请求 2 秒内进入 cancelling/cancelled，可等待外部服务实际终止但不再接受结果。
- 不存在永久 pending；租约异常最终在配置窗口内恢复或失败。
- 路径穿越和秘密泄露安全测试 100% 通过。
- Windows/macOS/Linux Mock smoke 100% 通过。

指标必须由自动测试或可重复脚本产生，不使用无法追溯的手工数字。

## 14. 下一 Sprint 可直接领取的任务

本 Sprint 以“平台硬化与 RC 证据”为目标；模块 Phase M3 已完成，后续按 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md) 执行：

| 顺序 | 工单 | 交付 | 验收 |
|---:|---|---|---|
| 1 | HARD-001/002 | Node/Python 工具链和依赖锁 | 新机器一次安装成功 |
| 2 | HARD-101..104 | Node/Module/Agent 共享契约 | 删除手写重复 Catalog |
| 3 | HARD-201..204 | schema_migrations ledger | 旧库升级/中断恢复通过 |
| 4 | HARD-301..304 | Provider 配置和秘密持久化 | UI 保存重启恢复、Key 不回显 |
| 5 | HARD-401..404 | Agent v1/v2、终点语义、审计和限额 | v2 冻结、超限前置阻断 |
| 6 | HARD-501..506 | 同 SHA CI 和真实 Provider UAT | run URL/report/产物可追溯 |
| 7 | HARD-601..604 | RC 版本、文档和发布演练 | `v1.0.0-rc.1` 可回滚发布 |

Sprint 出口：共享契约、迁移和配置持久化完成；同 SHA required checks 与真实主 Provider UAT 有证据；版本和运维文档一致。Seedream 未激活时保持 Optional/External Blocked。

## 15. 计划维护

- 本文件是唯一 Active 主计划；拆分工单后在表格增加 Issue/PR 链接和状态。
- `PROJECT-STATUS.md` 每个 Sprint Demo 后更新实测数据。
- 架构决策写入 `docs/architecture/adr/ADR-xxxx.md`，至少包括 NodeResult、map、Provider JobHandle、密钥存储和数据库升级策略。
- 需求变化先由 Product Owner 更新 PRD 和验收标准，再调整本计划，不允许仅在代码中改变行为。
- 工期变化超过 20%、P0 范围变化或外部 Provider 选择变化时，必须重新基线并记录版本。

## 16. Doubao Provider 增量计划（2026-09-21）

Doubao Seedream/Seedance 代码与离线契约已完成，但账号尚未激活对应模型。该增量不改变现有 Qwen Image + Wan3 默认发布路径。

执行顺序：`DOU-001 模型激活 → DOU-002 单能力 UAT → DOU-003 Workflow UAT → DOU-004..008 产品化收口`。

详细计划见 [`DOUBAO-SEEDANCE-PLAN.md`](DOUBAO-SEEDANCE-PLAN.md)。模型权限未解除前，不将 Doubao 加入 RC 必选门禁；但不得宣称其生产可用。

## 17. 模块化节点与 Seedream 产品专项（2026-09-22）

当前字段/端口自定义属于节点实例级能力；NodeKind、Catalog、图标、Compiler 和 Handler 仍是硬编码，不能直接称为模块平台。

批准的演进方向：

```text
BaseNodeKind（白名单执行器）
  → versioned ModuleDefinition（复用组件）
    → NodeInstance（画布实例覆盖）
```

Seedream 作为首个内置模块复用 `textToImage` Handler，将 Provider policy 锁定为 `doubao`。不新增 `seedream` NodeKind，不允许用户执行自定义代码。

执行顺序：

1. 先关闭 [`RC-CLOSURE-PLAN.md`](RC-CLOSURE-PLAN.md) 的 P0 门禁；
2. 再交付 ModuleDefinition、Registry、Schema-driven PropertyPanel 和 Seedream Mock/Contract 薄切片；
3. 最后实现用户 Module Designer、版本发布/升级和 Agent 模块发现。

详细计划见 [`MODULAR-NODE-SEEDREAM-PLAN.md`](MODULAR-NODE-SEEDREAM-PLAN.md)。预计两人约 3 周，单人约 4-5 周；首个 Seedream M0 薄切片为 5-7 天。

### 2026-09-22 验证结论

- 节点实例级字段/端口自定义通过。
- ModuleDefinition/Registry/Seedream definition 已有基础，但 Palette 未挂载、module drop/roundtrip/execution resolver 未接通。
- Agent validator/compiler/repair 通过 308 项专项测试，但自然语言 parser 仍是固定模板。
- 前后端 `textToImage` 端口 ID/cardinality 漂移是 P0，必须早于模块 E2E 和 Agent parser 修复。

专项报告见 [`../../reports/frontend-modularity-agent-validation-2026-09-22.md`](../../reports/frontend-modularity-agent-validation-2026-09-22.md)。

### 2026-09-23 升级判定

虽然 MOD-101～205 已提交，但 Subagent 复核和专项回归确认 10 个模块/Agent tools 测试失败，并存在 ExecutionResolver 不回写 Compiler、Designer API 不匹配、Agent Compiler 丢 module reference、RepairResult 契约错误等 P0。当前模块化成熟度下调为约 50%–55%。

后续任务按 [`MODULAR-NODE-SEEDREAM-PLAN.md`](MODULAR-NODE-SEEDREAM-PLAN.md) 的 Phase M0-R → M1-R → M2-R 执行；禁止继续以“文件/类已存在”作为完成标准，必须用 create→publish→drag→configure→save→reload→run 纵向证据关闭工单。

### 2026-09-28 第二轮验收与下一阶段

第二轮已完成 Seedream 前端模块纵向 E2E、module_usage 持久化和 structured Agent Parser/module gate。下一阶段切换为 Phase M3：扩展端口 Binding Designer、module-aware 前端图校验、真实 Mock Backend Playwright、Modify E2E、测试隔离、同 SHA CI 和 Seedream External UAT。

### 2026-10-12 校准

Phase M3（MOD-R3-001～005）已完成并有自动化证据；MOD-R3-006/007 已转入 HARD-501/502 与 HARD-505。模块化功能停止扩展，后续按 [`PLATFORM-HARDENING-PLAN.md`](PLATFORM-HARDENING-PLAN.md) 的 Epic H0-H6 收敛为 `v1.0.0-rc.1`。本专项（MODULAR-NODE-SEEDREAM-PLAN）不再是当前主战场。
