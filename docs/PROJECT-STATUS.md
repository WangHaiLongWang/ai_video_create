# ai_video_create 项目状态

> 基线日期：2026-09-28
> 状态版本：18.0
> 代码基线：`70daa1d` + 第二轮纵向验收工作区
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> RC 收敛计划：[`plans/active/RC-CLOSURE-PLAN.md`](plans/active/RC-CLOSURE-PLAN.md)
> 评估原则：区分代码存在、自动测试通过和真实外部服务可用；只记录当前环境可重复证据。

## 1. 结论

项目已进入“模块化主链可用、真实联调与高级自定义收敛”阶段。Module Palette/Designer、精确版本引用、Execution Materializer、Agent module-aware compiler、module_usage 和 Seedream 前端纵向 E2E 已完成基础验收；剩余重点是模块端口 Binding Designer、前端 module-aware 图校验、真实 Mock Backend 浏览器链路、测试隔离和真实 Provider UAT。

本轮校准纠正了旧状态中的三项错误：

- 当前日期是 2026-09-21、HEAD 是 `cc61b46`，旧文档记录的未来日期和不属于当前 HEAD 的基线不可作为证据。
- 后端完整测试仍不能在当前 venv 收集：Pillow 未安装；cryptography 已加入 requirements，但当前 venv 尚未同步安装。旧 Agent v1 acceptance 仍有 3 项失败。
- CI 只有三平台 unit/build 框架，没有 Playwright job；integration 命令使用 `|| true`，失败不会阻断 CI，因此不能视为已通过发布门禁。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 90% | 模块/Agent/执行层代码增多，单一契约和 wiring 仍不稳定 |
| React Flow 编辑器 | 94% | 实例级字段/端口/Edge 成熟，模块端口语义未完全接入 |
| 节点组件化 | 80% | Registry/API/Materializer/module_usage/Frontend E2E 已推进，高级端口和真实后端 E2E 待补 |
| Mock 执行闭环 | 90% | defaults/overrides 已进入 snapshot/Task，需浏览器连接真实 Mock Backend |
| Workflow Agent | 84% | structured parser、module-aware compiler/gate 已有第二轮测试，Modify 浏览器联调待验收 |
| Scene/Prompt 产品层 | 88% | Editor/Import/Export/Draft/Preview 已有 |
| 安全与秘密管理 | 83% | 安全代码存在，依赖环境和发布证据仍需修复 |
| Provider 与媒体 | 79% | Qwen/Wan3 有历史 UAT；Doubao External Blocked |
| 发布工程 | 78% | Playwright CI job 已有，仍缺同 SHA 运行证据与测试隔离修复 |
| 综合产品完成度 | **约 84%** | 第二轮纵向验收通过，仍未达到生产发布门槛 |

## 2. 当前可重复测试基线

当前环境：Windows、Node 22.21.1、npm 10.9.4、Python 3.12.3。

| 验证项 | 当前结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 22 files / 342 passed | 通过 |
| TypeScript | 0 errors | 通过 |
| Vite build | main 98.41 kB；最大 chunk 172.68 kB | 通过，无 500 kB 警告 |
| Chromium modules E2E | 3/3 passed；App+modules 14/14 passed | 通过，使用 API Mock |
| Backend 第二轮纵向集 | 173 passed / 1 warning | 通过 |
| Agent structured parser/module gate | 93 passed / 1 warning | 通过 |
| Backend full collection | 当前环境需重新复核 | 干净 venv 的 Pillow/cryptography 安装仍需验证 |
| Doubao Contract + Config | 16 passed | 通过 |
| All Provider tests | 44 passed | 通过 |
| Playwright CI | Mock FastAPI + Vite + Chromium job 已配置 | 尚无本次 run URL/同 SHA 证据 |

说明：第二轮 Windows 并行复测出现 `EMFILE`，串行模式暴露 Testing Library cleanup 污染；这属于测试隔离门禁，已进入 Phase M3。第二轮生产改动由定向 unit、typecheck、build 和 modules Playwright 3/3 覆盖。

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

### 3.0 组件化/Agent 最新判定

- 节点实例级自定义：通过。
- ModuleDefinition/Registry/Designer：代码和单测基础通过，但不能代表端到端组件化。
- Module 执行：P0；Resolver 未可靠回写 Compiler/Scheduler。
- Agent：编排基础通过；自然语言到 module-aware 可执行 Workflow 仍未通过。
- 最新审计：[`reports/workflow-componentization-audit-2026-09-23.md`](reports/workflow-componentization-audit-2026-09-23.md)。

第一轮 P0 开发已完成：ExecutionMaterializer、Workflow create/import roundtrip、Registry/Repository、Module API 乐观锁、Frontend module create/drop/property、Agent module-aware compiler、RepairResult 和四层 preview gate。定向 Backend module/agent/execution 回归 723 passed；Frontend 22 files / 342 tests passed，typecheck/build 通过。

第二轮新增：Workflow create/update/import/duplicate/delete 同步 module_usage；capability 过滤按 Provider Policy；Seedream 模块展示→拖入→override→刷新保真和 Designer create/save/publish 浏览器通过；Agent image-only、2 scenes×2 variants×5s、Seedream module ref、unknown/draft module gate 通过。

剩余关闭项：扩展端口 Binding Designer、module-aware 前端连接校验、真实 Mock Backend 浏览器联调、Modify E2E、Vitest EMFILE/串行污染治理、同 SHA CI 证据和真实 Seedream UAT。

### 3.0.1 2026-09-22 历史实现说明

9 月 22 日已完成 Manifest 对齐、module reference 字段、Palette/DnD、Resolver 和 structured parser 的代码骨架及分层测试；9 月 23 日纵向审计发现这些实现仍存在 wiring/契约断点，因此相关条目重新打开，不能再以“P0 已关闭”标记。

历史验证见 [`reports/frontend-modularity-agent-validation-2026-09-22.md`](reports/frontend-modularity-agent-validation-2026-09-22.md)，当前结论以 9 月 23 日审计为准。

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
