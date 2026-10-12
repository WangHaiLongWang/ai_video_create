# ai_video_create 项目状态

> 基线日期：2026-10-12
> 状态版本：20.0
> 代码基线：`869672b`（自 `44d2227` 以来仅文档变更；测试数字为 2026-10-10 实测，待同 SHA CI 复证）
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 当前推进计划：[`plans/active/PLATFORM-HARDENING-PLAN.md`](plans/active/PLATFORM-HARDENING-PLAN.md)（Epic H0-H6）
> 历史 RC 收敛计划（已被 PLATFORM-HARDENING-PLAN 取代）：[`plans/active/RC-CLOSURE-PLAN.md`](plans/active/RC-CLOSURE-PLAN.md)
> 评估原则：区分代码存在、自动测试通过和真实外部服务可用；只记录当前环境可重复证据。

## 1. 结论

项目已进入“模块化主链可用、真实联调与高级自定义收敛”阶段。Module Palette/Designer、精确版本引用、Execution Materializer、Agent module-aware compiler、module_usage 和 Seedream 前端纵向 E2E 已完成基础验收；本轮进一步关闭了模块端口 Binding Designer、module-aware 图校验、真实 Mock Backend 浏览器链路和测试隔离四项缺口。

本轮（Phase M3）已完成 MOD-R3-001/002/003/004/005：扩展端口 Binding 编辑、effective-ports 图校验（含前后端一致性与契约漂移清理）、Playwright 真实 Mock FastAPI 全链（零 route mock，Task/Asset 可查询）、Agent Modify 增量 diff 与破坏性确认（含真实浏览器验收）、Vitest 隔离治理。剩余重点是同 SHA CI 证据和真实 Provider UAT。

本轮校准以当前工作区实测为准：Playwright 全量 142 passed / 1 skipped / 0 failed（含 8 项真实 Mock FastAPI 浏览器链路；1 skipped 为 Scene JSON roundtrip），前端 387 passed，后端干净 venv 2123 passed / 8 skipped / 0 failed。尚不能替代同一 SHA 的 CI run 和真实 Provider UAT。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 92% | 模块/Agent/执行层完整，下一步消除共享契约和迁移债务 |
| React Flow 编辑器 | 97% | 实例字段/端口/Binding/effective-port 校验和 E2E 成熟 |
| 节点组件化 | 94% | 生命周期、Materializer、module_usage、真实 Mock Backend E2E 完成 |
| Mock 执行闭环 | 96% | 浏览器 create→publish→run、Task/Asset 查询通过 |
| Workflow Agent | 93% | structured parser、module compiler/gate、Modify增量Diff/E2E 完成 |
| Scene/Prompt 产品层 | 88% | Editor/Import/Export/Draft/Preview 已有 |
| 安全与秘密管理 | 83% | 安全代码存在，依赖环境和发布证据仍需修复 |
| Provider 与媒体 | 79% | Qwen/Wan3 有历史 UAT；Doubao External Blocked |
| 发布工程 | 84% | CI job和测试隔离完成，仍缺同 SHA run/UAT/发布演练 |
| 综合产品完成度 | **约 91%** | 功能主链成熟，进入平台硬化与 RC 证据阶段 |

## 2. 当前可重复测试基线

当前环境：Windows、Node 22.21.1、npm 10.9.4、Python 3.12.3。以下数字为 2026-10-10 实测（代码基线 `44d2227`，其后仅文档变更），**待同 SHA CI 复证**。

| 验证项 | 当前结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 22 files / 387 passed | 通过 |
| TypeScript | 0 errors | 通过 |
| Vite build | index 138.51 kB；最大 chunk 185.73 kB | 本轮复测通过，无 500 kB 警告 |
| Chromium modules E2E（真实 Mock FastAPI） | 5/5 passed | 通过，**零 route mock**，Task/Asset 可查询 |
| Chromium agent-modify E2E（真实 Mock FastAPI） | 3/3 passed | 通过，**零 route mock**，含 destructive 确认 |
| Playwright 全量 | 142 passed / 1 skipped / 0 failed | 通过 |
| Vitest 默认命令连续 2 次 | 375 passed × 2 | 通过 |
| Vitest 串行模式 | 375 passed | 通过 |
| Backend 广覆盖回归 | 677 passed | 通过 |
| Agent structured parser/module gate | 341 passed | 通过 |
| Backend full non-external（干净 venv） | 2123 passed / 8 skipped / 0 failed | 通过 |
| Backend 当前专项复测 | 153 passed / 1 warning | 本轮通过 |
| Doubao Contract + Config | 16 passed | 通过 |
| All Provider tests | 44 passed | 通过 |
| Playwright CI | Mock FastAPI + Vite + Chromium job 已配置 | 尚无本次 run URL/同 SHA 证据 |

### 2.1 浏览器门禁

1. 历史 deselect 和 multi-drag 失败已修复。
2. Modules E2E 现为 **5 项、零 route mock**，驱动真实 Mock FastAPI 完成 create→publish→drag→save→reload→run，并可查询 Task/Asset。
3. CI 已配置 Mock FastAPI + Vite + Chromium；仍需实际 Actions run URL、同 SHA 和 artifact。
4. Scene JSON roundtrip 仍需纳入 required checks。

### 2.2 测试隔离与限流（本轮修复）

- Vitest：显式 `afterEach(cleanup)` + `maxThreads: 2`，默认命令连续两次与串行模式均全绿。
- 发现并修复双层限流缺口：`DISABLE_RATE_LIMIT=1` 此前只对 `RateLimitMiddleware` 生效，`SecurityMiddleware` 仍返回 429，导致全量 E2E 失败；现已两层一致尊重该开关，并补 2 项回归测试。
- 发现并修复 handler 只写文件不写 `assets` 表的问题（`GET /api/assets` 此前恒为空），以及 `item_key` 为 None 时的崩溃。

### 2.3 后端环境与测试

- Pillow/cryptography 已进入 requirements；仍需要干净 venv 和三平台 CI 证明依赖可复现。
- 第二轮 module_usage/registry/parser/resolver 定向集 173 passed。
- Agent structured parser/module gate 定向集 93 passed。
- 完整 non-external pytest 需要在当前工作区重新归档，不沿用旧失败数字。

## 3. 前端实现评估

### 3.0 组件化/Agent 最新判定

- 节点实例级自定义：通过。
- ModuleDefinition/Registry/Designer：基础生命周期和前端 route-mock E2E 通过。
- Module 执行：Materializer 已接 REST/Scheduler，module_usage 已同步；真实 backend 浏览器执行仍待验收。
- Agent：structured parser、module-aware compile/gate 已有定向证据；Modify 浏览器联调仍待完成。
- 最新审计：[`reports/workflow-componentization-audit-2026-09-23.md`](reports/workflow-componentization-audit-2026-09-23.md)。

第一轮 P0 开发已完成：ExecutionMaterializer、Workflow create/import roundtrip、Registry/Repository、Module API 乐观锁、Frontend module create/drop/property、Agent module-aware compiler、RepairResult 和四层 preview gate。定向 Backend module/agent/execution 回归 723 passed；Frontend 22 files / 342 tests passed，typecheck/build 通过。

第二轮新增：Workflow create/update/import/duplicate/delete 同步 module_usage；capability 过滤按 Provider Policy；Seedream 模块展示→拖入→override→刷新保真和 Designer create/save/publish 浏览器通过；Agent image-only、2 scenes×2 variants×5s、Seedream module ref、unknown/draft module gate 通过。

剩余关闭项（与 §3.2 / §6 一致）：同 SHA CI 证据（RC-004）、真实 Qwen/Wan3 当前证据（RC-008）和真实 Seedream UAT（RC-007，外部阻断）。扩展端口 Binding、effective-ports 校验、真实 Mock Backend 联调、Modify E2E、Vitest 隔离治理已由 Phase M3 关闭。

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

| ID | 优先级 | 缺口 | 关闭标准 | 状态 |
|---|---:|---|---|---|
| FE-R3-001 | P0 | Module Designer 无扩展端口 Binding 编辑 | binding 可编辑、校验、发布、执行 | ✅ 完成 |
| FE-R3-002 | P0 | 前端连接校验仍依赖固定 NODE_CATALOG | 使用 effective module ports | ✅ 完成 |
| FE-R3-003 | P0 | modules E2E 使用 route mock | 真实 Mock FastAPI create→run | ✅ 完成 |
| FE-R3-004 | P1 | Vitest 并发 EMFILE/串行 DOM 污染 | 默认 npm test 连续稳定全绿 | ✅ 完成 |
| FE-R3-005 | P1 | Agent Modify 缺浏览器模块 Diff 验收 | 修改不重建、diff 可确认 | ✅ 完成 |

FE-R3-005 完成要点（MOD-R3-004）：

- **契约**：`AgentPreviewResponse` 增 `patch`/`diff`/`destructive`/`module_diffs`（added/removed/upgraded/reconfigured），前后端字段名经真实 API 冒烟核对一致。
- **修改不重建**：`NodeIntent.node_id` 透传，`compile_intent` 优先使用原 id（不再 `_deterministic_id(alias)`），LLM 往返后按 alias 还原；`apply-v2` 对已有 workflow 改为 `compute_graph_patch` + `apply_graph_patch` 增量应用；前端 `applyGraphPatch` 同步。实测 apply 后服务端节点/连线 id 原样保留。
- **Diff UI**：复活原死代码 `PatchPreview` 作为 modify 主视图（"变更内容（增量 Diff）"），新增 `ModuleDiffs` 区块与 `moduleId@moduleVersion` 徽标。
- **破坏性二次确认**：`alertdialog` 列出删除节点/连线，可取消（no-op）；与 `!can_apply` 验证失败横幅明确分离。
- **MockProvider 确定性**：modify prompt 返回保留拓扑 + 单点 config 变更，不再落入 `_template_fallback` 重建。
- **真实浏览器验收**：新增 `agent-modify.spec.ts` 3 项，零 route mock，驱动真实 Mock FastAPI。

FE-R3-001～004 完成要点：

- **FE-R3-001**：`ModulePort.binding` 类型、`collectPublishBlockers` 客户端门禁、PortsSection 渲染 `draft.ports` 并区分 core（锁定）/扩展（可增删改 + binding 下拉）、Publish 遇未绑定端口禁用、`parseResponse` 正确解析 422 `{code, errors}` 结构化错误。同时修复 baseKind 切换清空扩展端口的缺陷。
- **FE-R3-002**：新增 `getNodeEffectivePorts`（优先 `data.ports`，回退 `NODE_CATALOG`），两处校验器改为 port-map 驱动，新增 `UNKNOWN_HANDLE`，`validateConnection` 补环检查，使 connect/reconnect/start 结论一致；后端 `_effective_ports` 同步解析，无需重排执行管线。
- **FE-R3-003**：Playwright webServer 改为 Mock FastAPI + Vite 双服务，`modules.spec.ts` 零 route mock 完成 create→publish→drag→save→reload→run，Task/Asset 可查询；`AI_VIDEO_DB_PATH` 使 E2E 使用隔离 DB；doubao-pinned 模块在 mock-only 时回退 MockProvider。
- **FE-R3-004**：显式 `afterEach(cleanup)` + `maxThreads: 2`，默认命令连续两次与串行模式均 375 passed。

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
2. Pillow/cryptography 已声明，但干净环境安装证据和锁定策略仍不足。
3. 数据库 migration 缺少正式 `schema_migrations` 账本和失败恢复证明。
4. Provider 设置 API 主要修改内存，`.env` 仍是重启后的事实来源。
5. 旧 Agent v1 与 Agent v2 并存且 acceptance 行为不一致，需要兼容策略或下线计划。
6. Playwright/Backend 生命周期已进入 CI，仍缺真实 run 和 flaky/资源限制治理。

## 5. Provider 状态

| Provider | 代码状态 | 真实验证状态 |
|---|---|---|
| MiMo `mimo-v2.5-pro` | adapter/config 完成 | 有历史真实调用证据；当前未复测 |
| Qwen Image 3.0 | adapter/config 完成 | 有历史生图证据；当前未复测 |
| Wan3 Video | async job/poll/persist 完成 | 有历史 UAT；当前媒体依赖门禁未复现 |
| Doubao Seedream/Seedance 2.5 | image/video adapter、UI、Contract 完成 | Key/目录成功，账号未激活模型，External Blocked |
| ComfyUI | T2I 基础存在 | 当前环境未验证；I2V 仍非发布主路径 |
| Mock | 全能力基础 | 大部分测试通过；「旧 Agent acceptance 3 项失败」为 2026-09 历史记录，当前是否仍存在待复证 |

Doubao 详细计划见 [`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)。

## 6. 发布阻断项

| ID | 优先级 | 阻断项 | 当前证据 | 关闭标准 | 状态 |
|---|---:|---|---|---|---|
| RC-001 | P0 | 干净环境依赖证据缺失 | requirements 已更新 | 新 venv 完整 non-external suite | ✅ 关闭（2026-10-08 干净 venv 2096 passed / 0 failed） |
| RC-002 | P0 | 模块真实 Backend 浏览器链路缺失 | route-mock E2E 3/3 | create→publish→run 全绿 | ✅ 关闭（5/5 零 route mock） |
| RC-003 | P0 | Vitest 资源/隔离不稳定 | EMFILE 与 DOM 污染 | 默认命令连续两次全绿 | ✅ 关闭（375×2 + 串行全绿） |
| RC-004 | P0 | 无同一 commit CI 证据 | Playwright job 已配置 | 三平台 required checks + report URL | ⏳ 待办（HARD-501/502） |
| RC-007 | P1 | Doubao 模型未激活 | 两模型真实请求均 404 未激活 | 激活或配置 Endpoint 后 image/video/workflow UAT | ⏳ 外部阻断 |
| RC-008 | P1 | 真实 Qwen/Wan3 当前证据缺失 | 仅历史报告 | 当前 commit 受控 UAT 或明确从 RC 范围移除 | ⏳ 待办 |

RC-001 关闭证据（2026-10-08）：全新 venv 安装 `backend/requirements.txt`，`Pillow 12.3.0`、`cryptography 50.0.2`、`AESGCM` 均可导入；`pytest backend/tests -m "not external"` → **2096 passed / 8 skipped / 21 deselected (external) / 0 failed**。注意项目自带 `backend/.venv` 仍缺 Pillow（历史遗留），日常开发建议同步该 venv。此后 2026-10-10 的干净 venv 复测为 **2123 passed / 8 skipped / 0 failed**（新增 Phase M3 测试所致，非回退）；§2 基线表采用后者。

本轮顺带修复的已存在缺陷（非本轮引入，但已闭环）：

1. `TestExecutionResolverRejectsUnboundPorts` 2 项失败——测试夹具缺 `status="published"`，Resolver 正确要求模块已发布才可执行；已补夹具。
2. 双层限流缺口——`DISABLE_RATE_LIMIT=1` 只对 `RateLimitMiddleware` 生效，`SecurityMiddleware` 仍返回 429，导致全量 Playwright 失败；现已一致尊重该开关并补 2 项回归测试。
3. `imageToVideo` 输出基数契约漂移——统一为 FE `node-manifest.ts` 权威（`video` 输出 `cardinality='one'`），后端对齐并加契约 parity 测试。
4. `test_wan3_uat` 配置断言被本地 `.env` 影响（`AI_VIDEO_WAN3_MODEL=wan3.0-video-prime` 覆盖默认值）——改为构造不加载 `.env` 的 `Settings(_env_file=None)` 验证声明默认值。

## 7. 后续开发路线

当前主战场是平台硬化（Epic H0-H6），不再按旧 RC-0/RC-1/RC-2 节奏推进。工单明细、工作量与验收以 [`plans/active/PLATFORM-HARDENING-PLAN.md`](plans/active/PLATFORM-HARDENING-PLAN.md) 为准；主交付计划中的里程碑见 [`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md) §8。

### Sprint H1：可复现工具链 + 共享契约 + 迁移账本（3-4 天）

范围：Epic H0（HARD-001～004）、H1（HARD-101～104）、H2（HARD-201～204）。

- Node 22 / Python 3.12 工具链一致，可重复安装，清理未审批 warning。
- Node/Module/Workflow/Agent Catalog 共享同一来源，parity test 阻断漂移。
- `schema_migrations` ledger、checksum、事务化 runner、旧库无损升级与中断恢复。

出口：全新 venv 一次安装成功；前后端 Schema 单一来源；migration 有 ledger 与恢复证据。

### Sprint H2：Provider 持久化 + Agent 兼容层（3-4 天）

范围：Epic H3（HARD-301～304）、H4（HARD-401～404）。

- Provider 非秘密配置与 secret reference 持久化，重启恢复，GET 不回显 Key。
- 多 Provider CRUD、默认选择、测试连接；Workflow/Module 只保存 provider config ID。
- Agent v2 冻结、v1 弃用策略、Modify/Apply 审计、节点/费用限额前置阻断。

出口：UI 保存的 Provider 设置重启后仍在；Agent v1/v2 行为明确。

### Sprint H3：CI/UAT 与发布演练（2-3 天）

范围：Epic H5（HARD-501～506）、H6（HARD-601～604）。

- 触发同 SHA 三平台 CI + browser-e2e，归档 JUnit、Playwright report/trace、安全报告与 build。
- MiMo/Qwen/Wan3 当前 commit 最小真实 UAT（真实 job 保持 manual/nightly，非 PR 默认）。
- Doubao 未激活时保持 Optional/External Blocked，不阻断 Qwen+Wan3 RC。
- 统一版本/CHANGELOG/Known Issues，执行安装、升级、回滚、备份恢复演练。

出口：RC-004/RC-008 有同 SHA 证据；所有 P0 阻断关闭，P1 有明确延期批准和用户可见说明；`v1.0.0-rc.1` tag 只指向已验证 SHA。

模块化节点与 Seedream 专项（Phase M0-M3）已完成，详见 [`plans/active/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/active/MODULAR-NODE-SEEDREAM-PLAN.md)；不再安排新的模块功能 Sprint。

## 8. 文档导航

- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- 当前推进计划（平台硬化 H0-H6）：[`plans/active/PLATFORM-HARDENING-PLAN.md`](plans/active/PLATFORM-HARDENING-PLAN.md)
- 历史 RC 收敛计划（Superseded，见其头部说明）：[`plans/active/RC-CLOSURE-PLAN.md`](plans/active/RC-CLOSURE-PLAN.md)
- React Flow/Agent：[`plans/active/REACT-FLOW-AGENT-PLAN.md`](plans/active/REACT-FLOW-AGENT-PLAN.md)
- Flow/Scene：[`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- Doubao：[`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)
- 模块化节点与 Seedream：[`plans/active/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/active/MODULAR-NODE-SEEDREAM-PLAN.md)
- 测试报告：[`reports/`](reports/)

当前状态必须在 P0 门禁关闭后才能升级为 Release Candidate。
