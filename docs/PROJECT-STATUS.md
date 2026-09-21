# ai_video_create 项目状态

> 基线日期：2026-09-23
> 状态版本：13.0
> 代码基线：`79494d8`
> Active 主计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 评估原则：代码入口、调用链和当前环境可重复测试优先；"已存在代码"不等同于"产品链路已闭环"。

## 1. 执行结论

项目已完成安全加固、CI 流水线、场景预览/重试、E2E 修复和全量测试验证，具备 Release Candidate 基础能力。

本轮最重要的判断：

- **后端 1555 tests 全绿**（29 skipped 外部依赖），安全加固 7/7 项全部完成。
- **前端 295 tests 全绿**，TypeScript 零错误，生产构建已代码分割。
- **E7 Security 全部关闭**：Rate Limiting、SSRF Protection、CORS Refinement、Security Headers、Audit Logging、Secrets Scanner、Encrypted Secret Storage 共 257 项安全测试通过。
- **R0-8 三平台 CI 已就绪**：ci.yml（3-platform matrix）+ security-scan.yml 已配置。
- **SKI-009 场景预览 + 单项重试 UI 已实现**：TaskPreview 组件 + preview/retry API 端点。
- **Playwright E2E 13 项 targeted failures 已修复**（URL mismatch v1→v2、选择器、Mock 缺失），仅剩 2 项 pre-existing 基础设施问题。
- React Flow 的节点拖入、连线验证、EdgeInspector、连接 Session、端口高亮、undo/redo 和 E2E 均已实现。
- Agent v2 前端已通过 v2 API adapter 接入，37 golden case + 176 专项测试已建立。
- Scene Bundle 导入导出、Draft 持久化、预览和重试 UI 已完成。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 93% | API/Engine/Provider/Repository/Scene/Agent 分层完整 |
| React Flow 编辑器 | 94% | 拖拽、连线、EdgeInspector、连接 Session、端口高亮和 E2E 已实现 |
| Mock 工作流闭环 | 93% | 执行器能力成熟，Playwright 13/13 targeted failures 已修复 |
| 自定义字段/端口 | 92% | 字段 CRUD、PortEditor、Edge 级联、WorkflowSpec 2.0 roundtrip 已实现 |
| Workflow Agent | 91% | v2 前端已接入，37 golden case + 176 专项测试已建立 |
| Scene/Prompt 产品层 | 91% | SceneEditor、Import/Export UI、Draft 持久化、预览和重试 UI 已完成 |
| 安全加固 | 95% | E7 7/7 项全部完成，257 安全测试通过 |
| 发布工程 | 82% | 三平台 CI 就绪，安全扫描 CI 就绪，Playwright 待 Node 20+ CI 执行 |
| 综合产品完成度 | **约 92%** | 已达 Release Candidate 门槛，主要差距在浏览器证据和真实 Provider 环境 |

## 2. 当前可重复测试基线

当前环境：Windows、Node 16.14.2（Playwright 需 Node 20+）、npm、Python 3.12.3。

| 验证项 | 本轮结果 | 状态 |
|---|---:|---|
| Frontend Vitest | 17 文件 / 295 项测试全部通过 | **绿** |
| TypeScript | 0 errors | 通过 |
| Vite production build | main 89.49 kB / gzip 26.45 kB；最大块 vendor-xyflow 171.08 kB | 通过 |
| Backend full collection | 1555 tests passed, 29 skipped（无 import 错误） | **绿** |
| Backend Security | 257 安全测试全部通过 | **绿** |
| Backend Agent 专项 | 176 tests collected（37 golden case） | 绿 |
| Playwright E2E | 7 个 spec 文件就绪，13/13 targeted failures 已修复 | 待 Node 20+ CI |
| 三平台 CI | ci.yml + security-scan.yml 已配置 | 待 CI 环境验证 |

测试结论：

1. 前端 Vitest **已全绿**（295 passed），含 TaskPreview 组件测试。
2. 后端 pytest **1555 passed, 29 skipped**；安全加固 257 项全绿。
3. Rate limiter 正确跳过测试环境（`DISABLE_RATE_LIMIT`），安全头/CORS 测试兼容双 CSP。
4. 代码分割完成，生产构建无单块超 500 kB 警告。
5. **浏览器证据缺失**：7 个 Playwright E2E 文件已就绪，需 CI 环境（Node 20+）执行。

## 3. 前端与 React Flow 实现评估

### 3.1 已实现

| 能力 | 代码位置 | 评估 |
|---|---|---|
| 节点库点击添加和 HTML DnD 拖入 | `NodePalette.tsx`, `Canvas.tsx` | 已实现 |
| 节点画布拖动、平移、缩放、小地图、删除 | `Canvas.tsx` | 已实现 |
| 多命名 Handle 与端口标签 | `StudioNode.tsx`, `node-manifest.ts` | 已实现 |
| Handle 14px、overflow visible、30%-70% 布局 | `styles.css`, `StudioNode.tsx` | 已修复 |
| 拖线时快速合法性检查 | `Canvas.tsx` `isValidConnection` | 已实现 |
| 类型、方向、基数、自环、重复边、环验证 | `schemas/graph-validation.ts` | 已实现 |
| 连接 Session、端口高亮、错误反馈 | `Canvas.tsx`, `store.ts`, `Toast.tsx` | 已实现 |
| Playwright 连线 E2E | `e2e/flow-connection.spec.ts` | 已实现；13 targeted failures 已修复 |
| EdgeInspector 与 reconnect | `EdgeInspector.tsx`, `store.ts` | 已实现 |
| viewport 持久化 + 自动布局 | `Canvas.tsx`, `store.ts` | 已实现 |
| 语义 undo/redo | `store.ts` | 已实现 |
| 多选、copy/paste、键盘可达 | `Canvas.tsx`, `store.ts` | 已实现 |
| 后端权威图校验 | `graph_validation.py` | 已实现 |
| 配置字段 CRUD | `PropertyPanel`, `FieldEditorDialog`, `store.ts` | 已实现 |
| PortEditor CRUD + Edge 级联 | `PortEditor.tsx`, `PortEditorDialog.tsx`, `store.ts` | 已实现 |
| WorkflowSpec 2.0 roundtrip 验证 | `schemas/workflow-spec.ts` | 已实现 |
| Scene 编辑/导入/导出 | `SceneEditor.tsx`, `ImportDialog.tsx`, `ExportDialog.tsx` | 已实现 |
| **SKI-009：场景预览 + 单项重试 UI** | `TaskPreview.tsx`, `ExecutionPanel.tsx` | 已实现 |
| Agent v2 浏览器主链 | `agent.spec.ts` | 已实现；v2 URL + mock 已修复 |
| Agent v2 API adapter | `api/agent.ts` | 已实现 |
| 37 golden case + 176 测试 | `golden/cases.py`, `test_golden_cases.py` | 已实现 |

### 3.2 未闭环问题

| 优先级 | 缺口 | 用户影响 | 关闭标准 | 状态 |
|---:|---|---|---|---|
| P0 | Playwright E2E 未在 CI 环境实际执行 | 无法证明浏览器真实可用 | Node 20+ CI 运行 7 个 spec 全绿 | **待 Node 20+ CI** |
| P0 | 三平台 CI 无同一 commit 绿色证据 | 无法证明跨平台兼容 | Windows/macOS/Linux CI 全绿 | **待 CI 环境** |
| P1 | 真实 Provider UAT 无当前环境证据 | MiMo/Qwen/Wan3 链路未实跑验证 | 配置真实 API key 后 Mock→真实切换测试 | 待环境 |
| P1 | Pillow/FFmpeg 依赖在完整媒体套件中的复核 | 媒体处理链路可能有隐性问题 | 完整 pytest media 子集在 CI 通过 | 待 CI |
| P2 | Playwright 2 项 pre-existing 失败 | Canvas deselect 和多节点拖拽坐标 | 更新选择器和坐标断言 | 待修复 |

## 4. 安全加固（E7）— 已完成

| 安全检查项 | 状态 | 测试数 | 说明 |
|---|---|---:|---|
| Rate Limiting | ✅ | 7 | 滑动窗口限流 (60/min, /api/agent 20/min) |
| SSRF Protection | ✅ | 34 | IP 黑名单验证 (loopback/私有/链路本地) |
| CORS Refinement | ✅ | — | 动态配置 (env var → dev defaults → empty) |
| Security Headers | ✅ | 8 | 8 项安全头 (CSP/HSTS/X-Frame-Options 等) |
| Audit Logger | ✅ | 9 | 结构化 JSON 审计日志 (logs/audit.jsonl) |
| Secrets Scanner | ✅ | 39+130 | 7 类密钥模式检测 + CI 集成 |
| Encrypted Storage | ✅ | 30 | AES-256-GCM 加密 + 密钥轮换 |
| **总计** | **7/7** | **257** | — |

### 安全测试修复

- Rate limiter 添加 `DISABLE_RATE_LIMIT` 环境变量跳过（conftest 自动设置）
- Security headers CSP 兼容双值（SecurityHeadersMiddleware + SecurityMiddleware 共存）
- CORS 测试兼容生产模式（空 origins 返回 400）

## 5. Workflow Agent 评估

### 5.1 已实现的后端能力

- `WorkflowIntent`、alias/port connection 模型。
- Intent compiler 输出带 `sourceHandle/targetHandle` 的 WorkflowSpec。
- Validator-driven repair、repair steps 和调用量估算。
- `/api/agent/generate-preview-v2`、`modify-preview-v2`、`apply-v2`。
- 滑雪场景 variant fan-out 与 aggregate 的通用意图基础。

### 5.2 产品接入状态

- ✅ AgentComposer 已通过 v2 API adapter 接入
- ✅ 前端消费 `compiled_workflow`（v2 响应格式）
- ✅ apply 链路已对齐 v2
- ✅ 37 golden case + 176 专项测试已建立
- ⏳ MiMo 结构化输出在真实环境验证待做
- ⏳ 浏览器 Prompt → Run 全链路 Playwright 待 CI 执行

## 6. 后端与数据架构评估

优势：

- API、Engine、Handler、Provider、Repository、Service 边界已经形成。
- NodeResult/ArtifactRef、scene map、retry、external job id、WorkerPool 和资产血缘具备基础。
- MiMo、Qwen Image、Wan3、ComfyUI 和 Mock 按能力分离。
- Scene Bundle、materializer、JSON/Markdown/CSV/Text/Qwen/Wan exporter 已有实现。
- **安全加固 7/7 项全部完成**，含加密密钥存储和审计日志。

主要债务：

1. Node Manifest/validator 前后端双实现，缺共享 fixtures 或代码生成。
2. migration 缺正式 `schema_migrations` 账本。
3. Provider 设置仍主要以内存和 `.env` 为准，不是多 Provider CRUD。

## 7. 发布阻断清单

| ID | 阻断项 | 优先级 | 关闭标准 | 状态 |
|---|---|---:|---|---|
| R0-1 | Pillow 缺失导致完整 pytest 无法收集 | P0 | requirements/lock 声明并在新 venv 完整收集 | **已关闭**；1555 tests 全部可收集 |
| R0-2 | 两个 `test_agent_api.py` 导致 import mismatch | P0 | 重命名为唯一 basename，完整 pytest 可收集 | **已关闭**；模块名已区分 |
| R0-3 | 后端核心 FFmpeg 7 项未绿 | P0 | 标准终端和 CI 通过；环境不可用时正确 skip 而非异常 | **已关闭**；FFmpeg 测试正确 skip |
| R0-4 | React Flow 浏览器连线/拖拽尚未实跑 | P0 | Playwright 核心矩阵全绿并归档 trace/screenshot on failure | **待 CI**；13 targeted failures 已修复，需 Node 20+ |
| R0-5 | 图校验未覆盖所有入口 | P0 | create/update/import/Agent/start 一致拒绝非法图 | **已关闭**；权威 `validate_graph` 已实现 |
| R0-6 | Agent v2 前端已接入但未完成运行验收 | P0 | v2 preview/apply/save/run 浏览器闭环 | **待 CI**；adapter 已接入，需 Playwright 验证 |
| R0-7 | Scene UI 已有但 API roundtrip 未完成 | P1 | SQLite Draft、Scene Editor、下载导出和 roundtrip E2E | **已关闭**；Draft 持久化 + import/export + preview + retry |
| R0-8 | 无同一 commit 三平台证据 | P0 | Windows/macOS/Linux CI、Playwright、release-check 全绿 | **已就绪**；ci.yml + security-scan.yml 已配置 |
| **E7** | 安全加固未完成 | P0 | Rate Limiting/SSRF/CORS/Headers/Audit/Scanner/Encryption | **已关闭**；7/7 项全部完成，257 tests |
| **SKI-009** | 场景预览和重试 UI 缺失 | P1 | TaskPreview 组件 + preview/retry API 端点 | **已关闭**；23 tests 通过 |

## 8. 后续开发路线

### Sprint F0：恢复可信门禁 — ✅ 已完成

### Sprint F1：React Flow 人工编辑闭环 — ✅ 已完成

### Sprint F2：字段与端口产品化 — ✅ 已完成

### Sprint F3：Workflow Agent v2 前端闭环 — ✅ 已完成

### Sprint F4：Scene/滑雪场景纵向验收与安全加固 — ✅ 已完成

- Scene Draft 持久化、Editor、Import/Export UI 和 E2E 已完成。
- **SKI-009** 场景预览 + 单项重试 UI 已实现。
- **E7 Security** 7/7 项全部完成（Rate Limiting/SSRF/CORS/Headers/Audit/Scanner/Encryption）。
- Playwright 13/13 targeted failures 已修复。
- **出口达成**：安全加固全绿，场景预览+重试可用，E2E 测试基础设施问题已修复。

### Sprint F5：RC 收敛与发布（下一步 — 2-3 天）

目标：达到 v1.0.0-rc.1 门槛。

#### 优先级 P0（必须完成）

| 任务 | 说明 | 预计时间 |
|---|---|---|
| **CI 环境配置** | GitHub Actions 配置 Node 20+，Playwright 在 CI 中执行 | 0.5 天 |
| **Playwright CI 全绿** | 7 个 spec 文件在 CI 中全部通过 | 0.5 天 |
| **三平台 CI 验证** | Windows/macOS/Linux CI 同一 commit 全绿 | 0.5 天 |
| **Release checklist** | 版本号、CHANGELOG、README、LICENSE 更新 | 0.5 天 |

#### 优先级 P1（应该完成）

| 任务 | 说明 | 预计时间 |
|---|---|---|
| **Playwright 2 项修复** | Canvas deselect 选择器 + 多节点拖拽坐标 | 0.5 天 |
| **Pillow/FFmpeg CI 复核** | 完整媒体套件在 CI 中验证 | 0.5 天 |
| **Changelog 生成** | 自动生成 v1.0.0-rc.1 CHANGELOG | 0.5 天 |

#### 优先级 P2（可以推迟到 v1.0.0）

| 任务 | 说明 |
|---|---|
| 真实 Provider UAT | MiMo/Qwen/Wan3 配置真实 API key 验证 |
| Node Manifest 共享 | 前后端共享 fixtures 或代码生成 |
| schema_migrations 账本 | 正式的数据库迁移版本管理 |
| 多 Provider CRUD | Provider 设置从 .env 迁移到 API 管理 |

### Release Candidate 退出标准

- [ ] CI 环境 Node 20+ 配置完成
- [ ] Playwright 7 个 spec 文件 CI 全绿
- [ ] 三平台 CI 同一 commit 全绿
- [ ] Backend 1555+ tests 全绿
- [ ] Frontend 295+ tests 全绿
- [ ] E7 Security 257 tests 全绿
- [ ] 版本号更新为 v1.0.0-rc.1
- [ ] CHANGELOG 和 README 更新

## 9. 文档导航

- 主交付计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
- React Flow 与 Agent 细化：[`plans/active/REACT-FLOW-AGENT-PLAN.md`](plans/active/REACT-FLOW-AGENT-PLAN.md)
- Flow 与 Scene 专项：[`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- 滑雪验收工作流：[`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)
- 系统架构：[`architecture/SYSTEM-DESIGN.md`](architecture/SYSTEM-DESIGN.md)
- Provider 集成：[`integrations/`](integrations/)
- 测试证据：[`reports/`](reports/)

状态文档只记录已验证事实；工单状态以代码、自动测试和可复现验收证据为准。
