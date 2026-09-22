# ai_video_create 项目状态

> 基线日期：2026-09-22
> 状态版本：15.0
> 代码基线：`840daea`
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> RC 收敛计划：[`plans/active/RC-CLOSURE-PLAN.md`](plans/active/RC-CLOSURE-PLAN.md)
> 评估原则：区分代码存在、自动测试通过和真实外部服务可用；只记录当前环境可重复证据。

## 1. 结论

项目已进入内部 Beta / RC 前收敛阶段。React Flow 编辑、Workflow Agent v2、Scene 编辑导出、Mock 执行器、安全组件和多 Provider 架构的主体功能已经形成；RC 中的两项 Chromium 交互失败已在当前 HEAD 修复，但后端依赖环境和旧 Agent v1 acceptance 仍未闭环。

本轮校准纠正了旧状态中的三项错误：

- 当前日期是 2026-09-21、HEAD 是 `cc61b46`，旧文档记录的未来日期和不属于当前 HEAD 的基线不可作为证据。
- 后端完整测试仍不能在当前 venv 收集：Pillow 未安装；cryptography 已加入 requirements，但当前 venv 尚未同步安装。旧 Agent v1 acceptance 仍有 3 项失败。
- CI 只有三平台 unit/build 框架，没有 Playwright job；integration 命令使用 `|| true`，失败不会阻断 CI，因此不能视为已通过发布门禁。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 92% | API/Engine/Provider/Repository/Scene/Agent 分层清晰，契约仍有双实现 |
| React Flow 编辑器 | 94% | 连接、字段/端口、Edge、viewport 和浏览器主矩阵基本完成 |
| 前端产品闭环 | 94% | 两项交互失败已修复；全套 E2E 仍需重新运行并取消 roundtrip skip |
| Mock 执行闭环 | 88% | 执行器能力成熟，但旧 Agent v1 acceptance 有 3 项失败 |
| Workflow Agent | 89% | v2 preview/apply 浏览器用例通过；真实 MiMo 与完整运行仍待验收 |
| Scene/Prompt 产品层 | 88% | Editor/Import/Export/Draft/Preview 已有；后端联调 roundtrip 未形成浏览器证据 |
| 安全与秘密管理 | 83% | 中间件、扫描、审计、AES-GCM 代码和测试存在；cryptography 依赖未声明/未安装 |
| Provider 与媒体 | 79% | Qwen/Wan3 有历史 UAT；Doubao 合约完成但账号模型未激活 |
| 发布工程 | 73% | 依赖声明已部分修复；仍无 Playwright CI、integration 吞错和同 SHA 证据 |
| 综合产品完成度 | **约 89%** | 内部 Beta，可演示；未达到 RC |

## 2. 当前可重复测试基线

当前环境：Windows、Node 22.21.1、npm 10.9.4、Python 3.12.3。

| 验证项 | 当前结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 18 files / 311 passed | 通过 |
| TypeScript | 0 errors | 通过 |
| Vite build | main 98.41 kB；最大 chunk 172.68 kB | 通过，无 500 kB 警告 |
| Chromium Playwright | 定向复测 2/2 passed；全套基线仍为 132 passed / 2 failed / 1 skipped | 部分修复，需全套复跑 |
| Backend full collection | 1850 passed / 29 skipped | 通过（含 P0-4/5/6 新增 260 测试） |
| Backend 可运行集 | 1850 passed / 29 skipped / 0 failed | 全绿 |
| Doubao Contract + Config | 16 passed | 通过 |
| All Provider tests | 44 passed | 通过 |
| 三平台 CI | workflow 文件存在 | 尚无本次 run 证据 |

### 2.1 浏览器失败

1. `clicking canvas background deselects the selected node`（已修复，定向复测通过）
   - Page Object 点击 `.react-flow__viewport`，实际 pointer event 被 `.react-flow__pane` 拦截。
   - 应修改测试定位到 pane，同时确认产品的 `onPaneClick` 行为。
2. `multiple nodes can be dragged independently`（已修复，定向复测通过）
   - 第二个节点拖拽后 Y 坐标变化为 0。
   - 需要区分拖拽 helper/坐标断言不稳定，还是第二节点真实无法拖动。
3. Scene JSON roundtrip 用例仍处于 skip，不能计入闭环完成。

当前 Playwright 只自动启动 Vite，不启动 FastAPI；日志存在多次 `ECONNREFUSED 127.0.0.1:8000`。因此 132 项通过主要证明前端与 route mock 行为，不等同于真实前后端联调。

### 2.2 后端失败

- `Pillow>=10` 已写入 requirements，但当前 venv 未同步安装。
- AES-GCM 实现依赖 `cryptography`，已加入 requirements；当前 venv 尚未同步安装。
- 排除两个收集阻断后，3 项 `backend/tests/acceptance/test_e2e.py` 失败：旧 `/api/agent/generate` 在 Mock 模式返回 422，导致 generate/modify/explain 链路中断。
- 后端核心执行耗时约 4 分 28 秒，结果为 1521 passed、3 failed、20 skipped。

## 3. 前端实现评估

### 3.0 模块化与 Agent 专项判断（2026-09-22，P0 修复后）

- 节点实例级自定义通过：字段、端口、Edge、保存和 Undo 能力完整。
- ModuleDefinition、Seedream 内置 Registry、GET API 和 Schema Property UI 已实现，专项测试为 backend 62 passed（29 registry + 33 resolver）。
- **P0-1 已修复**：前后端 Manifest port ID/cardinality 统一为 `image` (one)。
- **P0-2 已修复**：NodeData/WorkflowSpec 保留 moduleId/moduleVersion/configOverrides，API roundtrip 通过。
- **P0-3 已修复**：ModulePalette 已挂载到 App.tsx，Canvas 支持 `application/reactflow-module` DnD。
- **P0-4 已修复**：Execution Resolver 接入 compiler/start，执行前验证模块存在性和配置。
- **P0-5 已修复**：MiMo 结构化 WorkflowIntent parser，支持 scene/variant 提取和 no-video 检测。
- **P0-6 已修复**：Parser golden cases 160 tests + backend E2E 20 tests，全绿。
- Agent compiler/validator/repair 专项 286 passed + 47 parser + 180 golden/E2E。

详细证据见 [`reports/frontend-modularity-agent-validation-2026-09-22.md`](reports/frontend-modularity-agent-validation-2026-09-22.md)。

### 3.1 已通过浏览器验证

| 能力 | 代码/测试 | 结论 |
|---|---|---|
| 节点点击添加、侧栏拖入、单节点移动 | `Canvas.tsx`, `flow-connection.spec.ts` | 通过 |
| 六条默认边和真实 Handle 拖线 | `StudioNode.tsx`, `flow-connection.spec.ts` | 通过 |
| 类型、自环、重复、环、基数拒绝 | graph validator + E2E | 通过 |
| 端口高亮、Toast、错误码 | Canvas/StudioNode/Toast | 通过结构和浏览器断言 |
| 字段 CRUD、校验、Undo | PropertyPanel/FieldEditorDialog | 通过 |
| 端口 CRUD、核心端口锁定 | PortEditor/PortEditorDialog | 通过 |
| 删除端口级联删除 Edge | store + fields-ports E2E | 通过 |
| 保存刷新后端口和 Edge 保留 | WorkflowSpec/store | 通过 |
| Agent v2 preview、warning、apply、cancel | AgentComposer + agent E2E | 通过 route mock |
| Scene Editor 编辑、锁定、添加 | SceneEditor + scene E2E | 通过 UI 验证 |
| Import/Export Dialog 基础交互 | dialogs + scene E2E | 通过 UI 验证 |

### 3.2 前端剩余缺口

| ID | 优先级 | 缺口 | 关闭标准 |
|---|---:|---|---|
| FE-RC-001 | P0 | 画布取消选择 E2E 失败 | 使用 pane locator，行为与测试均通过 |
| FE-RC-002 | P0 | 多节点独立拖拽 E2E 失败 | 两节点分别移动且坐标/Undo 正确 |
| FE-RC-003 | P0 | Scene roundtrip 被 skip | 启动真实 Mock backend，导出→导入结构等价 |
| FE-RC-004 | P0 | Playwright 未进入 CI | CI 启动 backend+frontend，135 项全绿并归档 trace |
| FE-RC-005 | P1 | E2E 中代理失败噪声 | 非错误态用例不得依赖 ECONNREFUSED fallback |
| FE-RC-006 | P1 | Settings/Provider 缺真实保存恢复 E2E | 设置保存、重启恢复、Key 不回显 |

## 4. 后端与架构评估

### 已完成

- `NodeResult`/`ArtifactRef`、Scheduler、WorkerPool、Retry、取消和失败传播。
- scene/variant map 与 aggregate，资产血缘和 external job ID。
- workflow create/update/import、Agent v1/v2 和 execution start 均调用权威图校验。
- Scene Draft SQLite repository、Bundle materializer、导入导出和安全扫描。
- Provider 按 text/image/video capability 分离：MiMo、Qwen、Wan3、Doubao、OpenAI、ComfyUI、Mock。
- Rate limiting、CORS、安全响应头、SSRF 策略、审计日志和秘密加密代码已存在。

### 架构债务

1. Node Manifest/graph validator 仍由前后端分别维护，需共享 fixtures 或代码生成。
2. `cryptography` 缺少依赖声明，安全模块无法在干净环境可靠安装。
3. 数据库 migration 缺少正式 `schema_migrations` 账本和失败恢复证明。
4. Provider 设置 API 主要修改内存，`.env` 仍是重启后的事实来源。
5. 旧 Agent v1 与 Agent v2 并存且 acceptance 行为不一致，需要兼容策略或下线计划。
6. CI integration 使用 `|| true`，会隐藏真实回归。
7. Playwright 与 backend 生命周期未统一编排。

## 5. Provider 状态

| Provider | 代码状态 | 真实验证状态 |
|---|---|---|
| MiMo `mimo-v2.5-pro` | adapter/config 完成 | 有历史真实调用证据；当前未复测 |
| Qwen Image 3.0 | adapter/config 完成 | 有历史生图证据；当前未复测 |
| Wan3 Video | async job/poll/persist 完成 | 有历史 UAT；当前媒体依赖门禁未复现 |
| Doubao Seedream/Seedance 2.5 | image/video adapter、UI、Contract 完成 | Key/目录成功，账号未激活模型，External Blocked |
| ComfyUI | T2I 基础存在 | 当前环境未验证；I2V 仍非发布主路径 |
| Mock | 全能力基础 | 大部分测试通过；旧 Agent acceptance 3 项失败 |

Doubao 详细计划见 [`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)。

## 6. 发布阻断项

| ID | 优先级 | 阻断项 | 当前证据 | 关闭标准 |
|---|---:|---|---|---|
| RC-001 | P0 | 后端依赖不可复现 | Pillow 未安装，cryptography 未声明 | 新 venv 安装 requirements 后完整收集 |
| RC-002 | P0 | Mock Agent acceptance 3 项失败 | `/api/agent/generate` 返回 422 | 明确 v1 兼容策略，完整 pytest 全绿 |
| RC-003 | P0 | 全套 Chromium 尚未复跑，Scene roundtrip 仍 skip | 定向 2/2 已通过 | 135/135 或经批准调整用例后全绿 |
| RC-004 | P0 | CI 无 Playwright job | `ci.yml` 未调用 test:e2e | backend+frontend E2E job 全绿 |
| RC-005 | P0 | integration 失败被吞 | 两处 `|| true` | 必选集失败必须阻断，external 单独标记 |
| RC-006 | P0 | 无同一 commit 三平台 run | 只有 workflow 配置 | 保存 Actions run URL/commit/artifact |
| RC-007 | P1 | Doubao 模型未激活 | 两模型真实请求均 404 未激活 | 激活或配置 Endpoint 后 image/video/workflow UAT |
| RC-008 | P1 | 真实 Qwen/Wan3 当前证据缺失 | 仅历史报告 | 当前 commit 受控 UAT 或明确从 RC 范围移除 |

## 7. 后续开发路线

### Sprint RC-0：恢复可信门禁（1-2 天）

- 声明 `cryptography`，使用干净 venv 安装 requirements。
- 修复旧 Agent v1 Mock acceptance 或将其迁移到 v2 契约。
- 全套复跑 Playwright，启用 Scene roundtrip。
- 删除 CI `|| true`；external 测试单独 job/手工触发。

出口：backend full pytest、frontend unit/type/build、Chromium E2E 全绿。

### Sprint RC-1：CI 与联调证据（1-2 天）

- 新增 Playwright CI job，同时启动 Mock FastAPI 和 Vite。
- Windows/macOS/Linux 运行 unit/type/build；Linux 运行浏览器和媒体 smoke。
- 归档 junit、Playwright report、trace、构建产物和安全报告。
- 修正 health probe，只使用存在的 `/api/health`。

出口：同一 commit 的 CI run 可追溯且没有吞错。

### Sprint RC-2：Provider 与发布决策（1-2 天）

- 复测 MiMo、Qwen、Wan3；真实外部测试保持显式、限额和非 PR 默认。
- Doubao 未激活时保持 Optional/Blocked，不阻断 Qwen+Wan3 RC。
- 生成 CHANGELOG、已知问题、安装/升级/回滚检查单。
- 冻结 `v1.0.0-rc.1` 范围并执行发布演练。

出口：所有 P0 阻断关闭，P1 有明确延期批准和用户可见说明。

### Product Sprint M0：模块化节点与 Seedream 薄切片（RC 后优先）

当前节点已经支持实例级字段/端口编辑，但还不是可复用模块。下一步不应继续增加硬编码 NodeKind，而应实现版本化 `ModuleDefinition → NodeInstance`：

1. 先冻结 ModuleDefinition/ModuleInstance JSON Schema 和前后端共享 fixture。
2. 将当前 `configSchema` 接入 Schema-driven PropertyPanel，统一 text/number/select/prompt/provider-model 等组件。
3. 增加 Module Registry 和 Module Palette；NodeInstance 保存 `moduleId/moduleVersion`。
4. 将自定义端口分为核心端口和有 binding 的扩展端口；无 binding 不得发布或执行。
5. 以 `builtin.seedream.text-to-image` 为首个模块，复用 `textToImage` Handler 和 `doubao` image Provider，不新增 Handler/NodeKind。
6. 模块发布版本不可变，升级必须生成 diff；缺少模块的旧工作流进入 degraded/read-only，而不是静默替换。

详细任务、数据模型、API、组件设计和验收见 [`plans/active/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/active/MODULAR-NODE-SEEDREAM-PLAN.md)。

## 8. 文档导航

- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- RC 收敛计划：[`plans/active/RC-CLOSURE-PLAN.md`](plans/active/RC-CLOSURE-PLAN.md)
- React Flow/Agent：[`plans/active/REACT-FLOW-AGENT-PLAN.md`](plans/active/REACT-FLOW-AGENT-PLAN.md)
- Flow/Scene：[`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- Doubao：[`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)
- 模块化节点与 Seedream：[`plans/active/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/active/MODULAR-NODE-SEEDREAM-PLAN.md)
- 测试报告：[`reports/`](reports/)

当前状态必须在 P0 门禁关闭后才能升级为 Release Candidate。
