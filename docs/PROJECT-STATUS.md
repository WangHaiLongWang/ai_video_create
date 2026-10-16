# ai_video_create 项目状态

> 基线日期：2026-10-16
> 状态版本：22.0
> 代码基线：Platform Hardening `78a99ac` + UAT 文档 `3241e93` + 当前验收收口变更
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 当前推进计划：[`plans/active/PLATFORM-HARDENING-PLAN.md`](plans/active/PLATFORM-HARDENING-PLAN.md)（Epic H0-H6）
> 历史 RC 收敛计划（已归档并被 PLATFORM-HARDENING-PLAN 取代）：[`plans/archive/RC-CLOSURE-PLAN.md`](plans/archive/RC-CLOSURE-PLAN.md)
> 评估原则：区分代码存在、自动测试通过和真实外部服务可用；只记录当前环境可重复证据。

## 1. 结论

项目的**本地可控 Platform Hardening 工程项已全部实现**：共享 Schema/Catalog、migration ledger、持久化多 Provider 配置、Agent 资源/费用门禁、失败演练、版本/备份恢复/发布工件均已落地。React Flow、模块化节点、Agent generate/modify/apply 和真实 Mock Backend 浏览器主链完成全量验收。

当前本机持久化默认路径已校准为 `openai_compat`（MiMo）→ `dashscope`（Qwen Image 3.0）→ `wan3`；三者 `/api/config/test-provider` 均返回 healthy，真实 Agent preview 返回六节点、`can_apply=true`、零校验错误。Doubao 保留为可选配置，未激活时不影响默认路径。

本轮（Phase M3）已完成 MOD-R3-001/002/003/004/005：扩展端口 Binding 编辑、effective-ports 图校验（含前后端一致性与契约漂移清理）、Playwright 真实 Mock FastAPI 全链（零 route mock，Task/Asset 可查询）、Agent Modify 增量 diff 与破坏性确认（含真实浏览器验收）、Vitest 隔离治理。剩余重点是同 SHA CI 证据和真实 Provider UAT。

2026-10-16 本机最终门禁：Frontend **24 files / 414 passed**，typecheck/build 通过；Backend non-external **2181 passed / 8 skipped / 21 deselected / 0 failed / 0 warning**；Chromium **143/143 passed**。MiMo→Qwen→Wan3 已在实现提交 `78a99ac` 受控复证；剩余发布边界只有远端同 SHA CI/制品归档和 Doubao 模型激活。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 100% | 共享契约、模块/Agent/执行层和正式迁移账本完成 |
| React Flow 编辑器 | 100% | 字段/端口/Binding/连线/持久化/导入导出全量 E2E 通过 |
| 节点组件化 | 100% | 生命周期、Materializer、usage、真实 Mock Backend E2E 完成 |
| Mock 执行闭环 | 100% | 浏览器 create→publish→run、Task/Asset 查询通过 |
| Workflow Agent | 100% | generate/modify/apply、增量 Diff、显式资产终点、限额完成 |
| Scene/Prompt 产品层 | 100% | Editor/Import/Export/Draft/Preview 和 JSON roundtrip 通过 |
| 安全与秘密管理 | 100% | AES-GCM、脱敏、多配置持久化、Trace、审计与 warning gate 完成 |
| Provider 与媒体（代码/Mock） | 100% | MiMo/Qwen/Wan3/Doubao 契约及失败演练完成 |
| 发布工程（本地可控） | 100% | 版本、constraints、备份恢复、manifest、checklist 完成 |
| RC 外部证据 | **未关闭** | 当前 SHA Actions/制品归档与 Doubao 激活依赖外部状态；真实主链已关闭 |

## 2. 当前可重复测试基线

当前验收环境：Windows、Node 22.21.1、npm 10.9.4、Python 3.12.3。`.nvmrc`、engines、runtime preflight 和 CI 已统一 Node 22；Python constraints 固定 3.12 验证依赖。

| 验证项 | 当前结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 24 files / 414 passed | 通过，无 React act warning |
| TypeScript | 0 errors | 通过 |
| Vite build | index 143.29 kB；最大 chunk 185.73 kB | 通过，无 500 kB 警告 |
| Chromium modules E2E（真实 Mock FastAPI） | 5/5 passed | 通过，**零 route mock**，Task/Asset 可查询 |
| Chromium agent-modify E2E（真实 Mock FastAPI） | 3/3 passed | 通过，**零 route mock**，含 destructive 确认 |
| Playwright 全量 | 143 passed / 0 skipped / 0 failed | 通过 |
| Vitest 默认命令连续 2 次 | 375 passed × 2 | 通过 |
| Vitest 串行模式 | 375 passed | 通过 |
| Backend 广覆盖回归 | 677 passed | 通过 |
| Agent structured parser/module gate | 341 passed | 通过 |
| Backend full non-external | 2181 passed / 8 skipped / 21 deselected / 0 failed / 0 warning | 通过 |
| Backend 当前专项复测 | 153 passed / 1 warning | 本轮通过 |
| Shared Catalog + Agent Trace | 119 passed / 1 warning | 本轮通过 |
| Doubao Contract + Config | 16 passed | 通过 |
| All Provider tests | 44 passed | 通过 |
| Real MiMo→Qwen→Wan3 | text + 1280×720 PNG + 2s/480P MP4 | 2026-10-12 本机通过，待正式报告/SHA归档 |
| Playwright CI | Node 22 + constraints + JUnit/build/Playwright/security artifacts 已配置 | 当前工作树尚未 push，缺最终 SHA run URL |

### 2.1 浏览器门禁

1. 历史 deselect 和 multi-drag 失败已修复。
2. Modules E2E 现为 **5 项、零 route mock**，驱动真实 Mock FastAPI 完成 create→publish→drag→save→reload→run，并可查询 Task/Asset。
3. CI 已配置 Mock FastAPI + Vite + Chromium；仍需实际 Actions run URL、同 SHA 和 artifact。
4. Scene JSON export→import roundtrip 已进入全量 Chromium（第 107 项）并通过。

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
- Agent：structured parser、module-aware compile/gate、Modify 增量 Diff/破坏性确认浏览器联调均完成。
- 最新审计：[`reports/workflow-componentization-audit-2026-09-23.md`](reports/workflow-componentization-audit-2026-09-23.md)。

第一轮 P0 开发已完成：ExecutionMaterializer、Workflow create/import roundtrip、Registry/Repository、Module API 乐观锁、Frontend module create/drop/property、Agent module-aware compiler、RepairResult 和四层 preview gate。定向 Backend module/agent/execution 回归 723 passed；Frontend 22 files / 342 tests passed，typecheck/build 通过。

第二轮新增：Workflow create/update/import/duplicate/delete 同步 module_usage；capability 过滤按 Provider Policy；Seedream 模块展示→拖入→override→刷新保真和 Designer create/save/publish 浏览器通过；Agent image-only、2 scenes×2 variants×5s、Seedream module ref、unknown/draft module gate 通过。

剩余关闭项（与 §3.2 / §6 一致）：同 SHA CI 证据（RC-004）和真实 Seedream UAT（RC-007，外部阻断）。RC-008 已由 `78a99ac` 真实链路关闭；扩展端口 Binding、effective-ports 校验、真实 Mock Backend 联调、Modify E2E、Vitest 隔离治理已由 Phase M3 关闭。

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

### Platform Hardening 关闭项

1. `schemas/base-node-manifest.json`、ModuleDefinition/Workflow JSON Schema 与 parity tests 已形成共享契约。
2. Node 22/Python 3.12、constraints、runtime preflight 和 CI 工具链一致。
3. `schema_migrations` ledger、checksum、事务回滚和 legacy adoption 已有自动测试。
4. Provider 多配置 CRUD/default/models/test、AES-GCM secret 与重启恢复已完成。
5. Agent v1 标记 deprecated；v2 有显式图片/视频终点、资源/费用 apply 前门禁。
6. 本地测试生命周期与 worker 策略已稳定；远端同 SHA run 单独列为外部发布证据。

## 5. Provider 状态

| Provider | 代码状态 | 真实验证状态 |
|---|---|---|
| MiMo `mimo-v2.5-pro` | adapter/config 完成 | **2026-10-12 当前链路复测通过**（`scripts/smoke_real_chain.py`，1 次文本调用 6.2s） |
| Qwen Image 3.0 | adapter/config 完成 | **2026-10-12 当前链路复测通过**（1 张 1280×720 PNG，1.47 MB，72.4s） |
| Wan3 Video | async job/poll/persist 完成 | **2026-10-12 当前链路复测通过**（2s/480P 图生视频，2.24 MB MP4，44.3s，external_job_id 已生成） |
| Doubao Seedream/Seedance 2.5 | image/video adapter、UI、Contract 完成 | 2026-10-16 health/目录成功；两模型真实最小请求均 404 未激活，External Blocked |
| ComfyUI | T2I 基础存在 | 当前环境未验证；I2V 仍非发布主路径 |
| Mock | 全能力基础 | 当前 Frontend/Backend/Chromium/acceptance 全量门禁通过；旧 Agent 失败仅为历史记录 |

Doubao 详细计划见 [`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)。

## 6. 发布阻断项

| ID | 优先级 | 阻断项 | 当前证据 | 关闭标准 | 状态 |
|---|---:|---|---|---|---|
| RC-001 | P0 | 干净环境依赖证据缺失 | requirements 已更新 | 新 venv 完整 non-external suite | ✅ 关闭（2026-10-08 干净 venv 2096 passed / 0 failed） |
| RC-002 | P0 | 模块真实 Backend 浏览器链路缺失 | route-mock E2E 3/3 | create→publish→run 全绿 | ✅ 关闭（5/5 零 route mock） |
| RC-003 | P0 | Vitest 资源/隔离不稳定 | EMFILE 与 DOM 污染 | 默认命令连续两次全绿 | ✅ 关闭（375×2 + 串行全绿） |
| RC-004 | P0 | 最终 commit 同 SHA CI 证据 | 本地 2181 backend + 414 frontend + 143 Chromium 全绿；CI/artifact 配置完成 | push 后三平台 required checks + run/artifact URL | ⛔ GitHub 443 超时（HARD-501/502） |
| RC-007 | P1 | Doubao 模型未激活 | 2026-10-16 复证：模型目录可见，但 Seedream/Seedance 最小真实请求均 404 未激活 | 激活或配置 Endpoint 后 image/video/workflow UAT | ⛔ 外部账号阻断 |
| RC-008 | P1 | 最终实现 commit 真实 Qwen/Wan3 证据 | `78a99ac` MiMo→Qwen→Wan3 全绿，产物 SHA-256、耗时、job ID、估算费用已归档 | 最终实现 SHA 受控 UAT | ✅ 关闭（2026-10-16） |
| RC-009 | P1 内容 | 滑雪教学固定器/后脚姿态不稳定 | 3 批 6 张真实 Qwen 图片人工检查；技术 2图→2视频→6.06s 合成通过 | 两张首帧同时满足“前脚固定、后脚踩雪、空后固定器可见” | ⛔ External Content Blocked（需局部重绘/ControlNet/换模型） |

RC-001 关闭证据（2026-10-08）：全新 venv 安装 `backend/requirements.txt`，`Pillow 12.3.0`、`cryptography 50.0.2`、`AESGCM` 均可导入；`pytest backend/tests -m "not external"` → **2096 passed / 8 skipped / 21 deselected (external) / 0 failed**。注意项目自带 `backend/.venv` 仍缺 Pillow（历史遗留），日常开发建议同步该 venv。此后 2026-10-10 的干净 venv 复测为 **2123 passed / 8 skipped / 0 failed**（新增 Phase M3 测试所致，非回退）；§2 基线表采用后者。

本轮顺带修复的已存在缺陷（非本轮引入，但已闭环）：

1. `TestExecutionResolverRejectsUnboundPorts` 2 项失败——测试夹具缺 `status="published"`，Resolver 正确要求模块已发布才可执行；已补夹具。
2. 双层限流缺口——`DISABLE_RATE_LIMIT=1` 只对 `RateLimitMiddleware` 生效，`SecurityMiddleware` 仍返回 429，导致全量 Playwright 失败；现已一致尊重该开关并补 2 项回归测试。
3. `imageToVideo` 输出基数契约漂移——统一为 FE `node-manifest.ts` 权威（`video` 输出 `cardinality='one'`），后端对齐并加契约 parity 测试。
4. `test_wan3_uat` 配置断言被本地 `.env` 影响（`AI_VIDEO_WAN3_MODEL=wan3.0-video-prime` 覆盖默认值）——改为构造不加载 `.env` 的 `Settings(_env_file=None)` 验证声明默认值。

### 6.1 真实链路 UAT 证据（2026-10-12）

最小真实链路 **MiMo → Qwen Image → Wan3** 已在当前工作区跑通，命令：`python scripts/smoke_real_chain.py chain`（脚本本轮新增，支持 `health` / `models` / `chain` 三种模式，调用量上限 1 文本 + 1 图 + 1 视频）。

| 步骤 | 结果 | 耗时 | 产物 |
|---|---|---:|---|
| MiMo `mimo-v2.5-pro` 文本 | ✅ | 6.23s | 1 条 image_prompt |
| Qwen `qwen-image-3.0` 生图 | ✅ | 72.43s | `data/uat/20261012-112731/scene-001-variant-01.png`（1280×720，1,471,278 bytes） |
| Wan3 `wan3.0-video` 图生视频 | ✅ | 44.29s | `data/uat/20261012-112731/scene-001-variant-01.mp4`（2s / 480P，2,242,752 bytes，external_job_id `2951b7d9-…`） |

前置健康探测（`health` 模式，调用各 Provider `health_check()`）三家均 `healthy: true`。

**顺带发现的配置缺陷（需修复，见下）**：`.env` 中 `AI_VIDEO_OPENAI_COMPAT_MAX_TOKENS=1048576`，超过 MiMo 上限（completion tokens 最大 131072），导致 `chat/completions` 直接返回 **HTTP 400 "max_completion_tokens is too large"**。这意味着 **任何走 MiMo 的文本调用（分镜、Agent intent）在当前 `.env` 下都会失败**，与 Provider 代码无关。smoke 脚本已做钳位绕过（`min(settings, 8192)`），根治需二选一：

1. 将 `.env` 中该值改为合理值（建议 4096，与 `Settings` 默认一致）；
2. 在 `OpenAICompatProvider` 构造时按模型上限校验/钳位，非法值直接报配置错误而不是打到 API 才 400。

历史证据和 `78a99ac` 最终实现提交复证均已整理到 [`reports/real-chain-uat-2026-10-12.md`](reports/real-chain-uat-2026-10-12.md)，包含模型参数、耗时、字节数、SHA-256、脱敏 job ID 与配置估算费用。供应商实际账单不由 API 返回，财务核账以控制台为准，不阻断技术 UAT。

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

模块化节点与 Seedream 专项（Phase M0-M3）已完成并归档，详见 [`plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md)；不再安排新的模块功能 Sprint。

## 8. 文档导航

- 长远路线图（v1.0 后 12-18 个月，方向层）：[`plans/active/ROADMAP.md`](plans/active/ROADMAP.md)
- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- 当前推进计划（平台硬化 H0-H6）：[`plans/active/PLATFORM-HARDENING-PLAN.md`](plans/active/PLATFORM-HARDENING-PLAN.md)
- 历史 RC 收敛计划：[`plans/archive/RC-CLOSURE-PLAN.md`](plans/archive/RC-CLOSURE-PLAN.md)
- React Flow/Agent 历史专项：[`plans/archive/REACT-FLOW-AGENT-PLAN.md`](plans/archive/REACT-FLOW-AGENT-PLAN.md)
- Flow/Scene 历史专项：[`plans/archive/FRONTEND-FLOW-SCENE-PLAN.md`](plans/archive/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- Doubao：[`plans/active/DOUBAO-SEEDANCE-PLAN.md`](plans/active/DOUBAO-SEEDANCE-PLAN.md)
- 模块化节点与 Seedream 历史专项：[`plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md`](plans/archive/MODULAR-NODE-SEEDREAM-PLAN.md)
- 测试报告：[`reports/`](reports/)

当前状态必须在 P0 门禁关闭后才能升级为 Release Candidate。
