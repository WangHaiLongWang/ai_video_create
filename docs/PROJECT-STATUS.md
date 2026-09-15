# ai_video_create 项目状态报告

> 基线日期：2026-09-15
> 状态版本：3.0
> Active 计划：`docs/plans/2026-09-15-company-delivery-plan.md`
> 评估口径：以代码审计、可重复测试和端到端用户链路为准；文件存在不等于功能完成。

## 1. 管理摘要

项目已从初始画布原型进入“执行链集成 + 真实 Provider 验证”阶段。工作流编辑、SQLite 持久化、任务队列、结果保存、执行状态轮询、资产记录、Provider 设置和模板入口均已形成代码路径；Qwen Image 3.0 已完成一次真实 1280×720 生图，Wan3.0 已完成官方协议配置、运行时注册、鉴权检查和 Contract Test。

当前仍不能定义为“真实提示词一键成片”产品。主要差距不是缺少 Provider，而是场景数据映射、长任务恢复、真实 Wan3 UAT、FFmpeg 合成验证和前端资产/错误体验尚未完成。

### 当前评分

| 维度 | 完成度 | 说明 |
|---|---:|---|
| 架构骨架 | 75% | 主要模块和 API 已存在，部分契约仍分散 |
| Mock 用户闭环 | 60% | 前端已调用后端执行，但 scene item 映射仍不完整 |
| 真实多模态闭环 | 50% | Qwen 生图已验证，Wan3 未执行计费 UAT，合成未验收 |
| Agent/模板体验 | 45% | 后端服务和入口存在，AgentComposer 仍使用本地规则 |
| 发布就绪度 | 40% | 测试基线恢复，缺浏览器 E2E、三平台和恢复演练 |
| 综合产品完成度 | **约 55%** | 可继续内部开发，不建议对外发布 |

### 当前阶段

```text
Phase A 类型化画布       65%  █████████████░░░░░░░
Phase B Mock 执行器      60%  ████████████░░░░░░░░
Phase C 真实多模态       50%  ██████████░░░░░░░░░░
Phase D Agent 与模板     45%  █████████░░░░░░░░░░░
Phase E 发布验收         40%  ████████░░░░░░░░░░░░
```

百分比表示阶段验收标准满足程度，不表示代码行数或已消耗工时。

## 2. 可重复验证基线

环境：Windows、Node 16.14.2、Python 3.12.3。

| 检查 | 最新结果 | 状态 |
|---|---:|---|
| 前端 Vitest | 16 passed | 通过 |
| 后端 Pytest | 226 passed、6 skipped | 通过（FFmpeg 环境项跳过） |
| TypeScript | `tsc --noEmit` | 通过 |
| Vite 生产构建 | JS gzip 约 124 KB | 通过 |
| FastAPI 健康检查 | HTTP 200 | 通过 |
| Qwen Image 鉴权/模型 | `qwen-image-3.0` | 通过 |
| Qwen Image 真实生图 | 1280×720 PNG | 通过 |
| Wan3 鉴权/endpoint | Provider health true | 通过 |
| Wan3 Contract Test | 480P、首帧、轮询、下载、参数校验 | 通过 |
| MiMo/OpenAI-compatible Contract Test | 认证头、模型、token 参数和采样参数 | 通过 |
| MiMo 真实文本调用 | `mimo-v2.5-pro`，HTTP 200，finish_reason=stop | 通过 |
| Wan3 真实视频 | 未创建计费任务 | 未验收 |
| FFmpeg 真实媒体 | 本机未安装，6 项跳过 | 未验收 |
| 浏览器 E2E | 未配置 Playwright | 未实现 |
| macOS/Linux smoke | 无 CI matrix 证据 | 未验证 |

测试仍有一条 Starlette TestClient 弃用警告，不影响当前通过结果，但需要在依赖升级前处理。

## 3. 当前默认产品配置

```text
LLM       openai_compat / Xiaomi MiMo / mimo-v2.5-pro（本机 Token Plan Key 已配置）
Image     dashscope / qwen-image-3.0 / 1280x720
Video     wan3 / wan3.0-video / 480P / adaptive / 5s
Fallback  ComfyUI（本地可选，但 img2vid workflow 仍为占位模板）
Storage   data/assets
Database  data/ai_video_create.db
Host      127.0.0.1
```

生产环境应使用百炼业务空间专属地址；目前配置为官方仍支持的公共北京 endpoint。集成详情见：

- `docs/integrations/qwen-image-3.0.md`
- `docs/integrations/wan3-video.md`

## 4. 功能矩阵

| 产品能力 | 状态 | 可用范围 | 主要证据/缺口 |
|---|---|---|---|
| 画布拖动、缩放、平移、删除 | 已实现 | 前端 | React Flow |
| 从侧栏拖入节点 | 部分 | 当前为点击添加 | 未实现 HTML DnD |
| 类型化连线 | 已实现 | 前端相等类型检查 | 后端共享 Manifest 缺失 |
| 节点属性配置 | 已实现 | 通用 key/value 表单 | 缺节点 Schema 驱动表单 |
| Undo/Redo | 已实现 | 30 状态 | 拖动过程可能污染历史 |
| localStorage 恢复 | 已实现 | 单一当前工作流 | 缺工作流切换管理 |
| SQLite 工作流 CRUD | 已实现 | 创建/读取/更新/删除/复制 | 更新仍接收裸 dict |
| 导入/导出 API | 已实现 | 后端/API client | 缺 UI 入口 |
| 自动保存 | 部分 | 1 秒防抖 | 失败仅 console，UI 仍显示已保存 |
| DAG 拓扑/环检测 | 已实现 | 编译时 | 保存时校验不足 |
| map task 展开 | 部分 | 按 storyboard 配置预展开 | 不是按实际输出动态展开 |
| task result 持久化 | 已实现 | `result_json` | 缺正式 NodeResult Schema |
| 上游结果读取 | 已实现 | Worker context | scene 对应输入仍不完整 |
| 执行收敛 | 已实现 | completed/failed/cancelled 汇总 | 深层失败传播仍需验证 |
| 自动重试 | 部分 | 固定最多 3 次 | 无错误分类、退避和人工 retry API |
| 取消执行 | 部分 | API 可改状态 | 外部 Provider 无持久 CancellationToken |
| Worker 租约/恢复 | 部分 | heartbeat/orphan 函数 | task_id 与资产幂等未完成 |
| 多 Worker | 未实现 | 当前单 Worker | 配置值未形成进程内 Worker pool |
| 前端运行后端 DAG | 已实现 | 保存、启动、轮询 | 尚未使用 WebSocket 主路径 |
| WebSocket 后端 | 已实现 | 事件推送/补拉 | 前端未订阅 |
| 节点执行状态 | 部分 | waiting/running/completed/failed | blocked/skipped/cancelled UI 不完整 |
| Qwen Image 3.0 | 已验证 | 真实 T2I | 多镜头工作流 UAT 未完成 |
| Wan3.0 Video | 已接入未 UAT | 首帧生视频 Contract | 未创建真实计费任务 |
| ComfyUI 生图 | 代码存在 | 基础 SDXL workflow | 未连接本机服务验证 |
| ComfyUI 图生视频 | 占位 | 不可用于生产 | workflow 只有 LoadImage/TextEncode |
| FFmpeg | 代码存在 | 检测/图转视频/拼接/ffprobe | 本机无可执行文件 |
| Asset 表/API | 已实现 | 列表、详情、血缘、统计 | Handler 资产登记一致性需 E2E |
| 资产文件服务 | 已实现 | `/assets` 静态目录 | 仍需统一下载/删除策略 |
| Provider 设置 | 已挂载 | Qwen/Wan3/ComfyUI/OpenAI/Ollama | API 只改内存，重启依赖 `.env` |
| 自定义 LLM | 已验证 | OpenAI-compatible，MiMo v2.5 Pro Token Plan 预设 | Provider 已注册、Key 未暴露，真实 Chat Completions 通过 |
| 模板 API/持久化 | 已实现 | 内置 + SQLite 自定义模板 | 前端选择后未装载返回 spec |
| Agent 后端 | 原型 | generate/modify/explain/patch | 非严格 tool calling/schema output |
| Agent 前端 | 未接后端 | 本地正则和默认模板 | 无 diff、确认、解释 |
| 安全中间件 | 已注册 | 本机基础 headers/body/rate | SSRF/流式 body limit 仍需加固 |

## 5. 代码架构

### 5.1 前端

```text
frontend/src
├── App.tsx                         应用壳、快捷键
├── store.ts                       画布、历史、保存、执行轮询
├── api.ts                         Workflow/Execution/Agent/Template/Asset/Config API
├── workflow.ts                    节点目录和默认工作流
├── types.ts                       Workflow 类型
├── StudioNode.tsx                 节点外观
└── components/
    ├── Canvas.tsx                 React Flow 画布
    ├── NodePalette.tsx            节点列表
    ├── PropertyPanel.tsx          节点配置/运行摘要
    ├── TopBar.tsx                 运行、设置、模板入口
    ├── AgentComposer.tsx          本地规则 Agent，待接后端
    ├── SettingsPanel.tsx          Provider 参数 UI
    └── TemplateSelector.tsx       模板浏览，返回结果未装载
```

前端已经从纯 Mock 动画切换为真实 Execution API 轮询，但执行状态逻辑仍集中在 `store.ts`。后续应拆分 `workflowStore` 与 `executionStore`，并将 WebSocket、断线恢复和事件去重隔离到 execution 层。

### 5.2 后端

```text
backend/app
├── main.py                         FastAPI 装配、Provider 和 Worker 生命周期
├── config.py                       AI_VIDEO_* 配置
├── models.py                       Workflow/GraphPatch 模型
├── middleware.py                   安全中间件
├── api/                            Workflow/Execution/Asset/Agent/Template/Config
├── db/
│   ├── connection.py              SQLite 单例和简易迁移执行
│   └── migrations/001-005         初始表、result、asset、template、attempt
├── repositories/                   Workflow、Asset
├── engine/
│   ├── compiler.py                拓扑和静态 map 展开
│   ├── queue.py                   claim/lease/result/retry/convergence
│   └── worker.py                  上游结果、Handler 和事件
├── handlers/                       Mock/Real 六类节点 Handler
├── providers/
│   ├── mock_provider.py
│   ├── ollama_provider.py
│   ├── openai_provider.py
│   ├── dashscope_provider.py      Qwen Image 3.0
│   ├── wan3_provider.py           Wan3.0 Video
│   └── comfyui_provider.py        本地 ComfyUI
└── services/                       Agent/Template/Event/Asset/FFmpeg
```

### 5.3 正确架构边界

- Qwen Image 与 Wan3 都属于阿里云百炼，但分别是 image/video capability Provider。
- Wan3 不是 ComfyUI 模型配置；`wan3` 与 `comfyui` 必须独立注册和选择。
- Handler 接收标准 NodeInput 并返回 NodeResult；Provider 只负责外部协议。
- 长任务 task_id 必须由 Scheduler/NodeRun 持久化，不能只存在于单次 Provider 协程内。
- 资产文件必须落本地，外部 24 小时临时 URL 不能成为工作流永久输出。

## 6. 已完成的重要改进

### 工程基线

- 修复 Workflow/Asset DELETE 204 空响应，FastAPI 可正常导入。
- Settings 使用 `AI_VIDEO_` 前缀，避免系统 DEBUG/HOST 污染。
- 安装并配置 pytest-asyncio，async 测试会真实执行。
- SecurityMiddleware/InputSanitizeMiddleware 已注册。
- pytest fixture loop scope 已显式设为 function。

### 执行与数据

- task 增加 result_json 和 attempt。
- Worker 保存 Handler 结果、读取上游结果，并拒绝把业务 error 标为 completed。
- executions 可在所有 task 进入终态时收敛。
- Assets 和 Templates 已增加 SQLite 表与 API。
- 前端运行按钮已调用后端执行 API并轮询任务。

### 多模态 Provider

- Qwen Image 使用官方 DashScope 3.0 同步/异步 endpoint，支持 URL 下载、尺寸和扩展参数校验。
- Qwen Image 已真实生成测试 PNG。
- Wan3 使用官方异步 video-synthesis endpoint，支持首帧 Base64、task_id 轮询和 MP4 下载。
- Wan3 默认 480P，开放 480P/720P/1080P、比例、时长、音频、seed、提示词增强和水印。
- Wan3 与 ComfyUI 拆分为两个 Provider。

### 自定义 LLM

- 新增 text-only `openai_compat` Provider，支持自定义名称、Base URL、模型、认证 Header/前缀、token 参数名、temperature、top_p、最大输出和 timeout。
- 当前本机预设为 Xiaomi MiMo `mimo-v2.5-pro`，使用 Token Plan Base URL 和 `api-key` 认证头。
- MiMo Provider 已注册，API Key 不出现在 Settings GET；真实 `/models` 和 Chat Completions 调用均已通过。

## 7. 当前 P0 风险

| ID | 风险 | 影响 | 当前证据 | 处置 |
|---|---|---|---|---|
| P0-1 | scene 数据未真正一一映射 | 图片/视频可能使用空 prompt 或错误上游资产 | compiler 让 map item 依赖上游全部 task | 优先实现动态 map/按 item_key 输入组装 |
| P0-2 | 长任务 task_id 不持久化 | 进程重启后可能重复计费创建 Wan3 任务 | task_id 只在 Provider 协程内 | NodeRun 增加 external_job_id/status |
| P0-3 | 真实 Wan3 未 UAT | 无法确认业务空间授权、实际结果格式和耗时 | 只做健康/Contract Test | 需用户确认费用后执行 480P/2 秒测试 |
| P0-4 | 无 FFmpeg 环境验收 | 最终多段视频无法确认可合成 | 6 项测试 skipped | 安装固定版本并执行真实媒体测试 |
| P0-5 | 失败传播仅直接一层 | 深层 task 可能永久 pending | queue fail_task 只更新直接依赖 | Scheduler 递归传播并做不变量测试 |
| P0-6 | 取消可能被晚到结果覆盖 | UI/数据库状态不一致 | Provider 缺持久 cancel token，complete UPDATE 未限制状态 | 状态条件更新 + Job cancel |
| P0-7 | 配置只在内存修改 | UI 保存后重启丢失 | Config API 注释明确 in-memory | ProviderConfig Repository/secret reference |
| P0-8 | Agent/模板入口未闭环 | 用户操作看似成功但画布不变 | TemplateSelector 丢弃返回 spec；AgentComposer 不调 API | 作为产品集成 Sprint 处理 |

## 8. 里程碑状态

| 里程碑 | 目标 | 状态 | 出口标准 |
|---|---|---|---|
| M0 工程基线 | App 可启动、测试可信 | 基本完成 | 增加 CI jobs 后关闭 |
| M1 编辑闭环 | 类型化画布、持久化、导入导出 | 进行中 | 共享 Schema + UI 入口 + 保存错误态 |
| M2 Mock 执行闭环 | scene/image/video/final 数据真实传递 | 进行中 | 浏览器 E2E、失败/取消/恢复通过 |
| M3 真实多模态 | MiMo → Qwen → Wan3 → FFmpeg 可播放成片 | 进行中 | MiMo/Wan3 计费 UAT + FFmpeg 合成验收 |
| M4 Agent/模板 | 自然语言生成/修改、diff、确认 | 未达门禁 | 前端接后端 + Schema output + 乐观锁 |
| M5 Release Candidate | 三平台、安全、恢复、文档 | 未开始 | Release checklist 全绿 |

## 9. 后续统筹计划

### Sprint N：执行语义收敛（最高优先级，预计 2 周）

目标：证明 3 个 scene 从实际 Storyboard 结果生成 3 个正确图片输入和 3 个正确视频输入。

1. 冻结 `NodeInput/NodeResult/NodeError/ArtifactRef` Schema。
2. 迁移 node_runs：input_json、result_json、external_job_id、attempt、error_code、timestamps。
3. Scheduler 按实际 storyboard output 创建/激活 map item。
4. textToImage 取得对应 `scene.image_prompt`；imageToVideo 取得对应 image path 与 `scene.video_prompt`。
5. VideoConcat 按 scene.index 聚合 video assets。
6. 深层失败递归传播，无永久 pending。
7. complete/fail 使用状态条件更新，修复取消竞态。
8. 配置 2 Worker 并验证原子 claim。
9. 增加 Mock 数据值断言，不只断言 task 数量/状态。

出口标准：Mock 浏览器链路输出 final asset；每项上下游内容与 scene_id 可追溯；重试/取消/重启收敛。

### Sprint N+1：真实媒体 UAT（预计 1-2 周）

目标：生成一套最小真实成片并形成可重复 UAT 记录。

1. 配置百炼 Workspace 专属 endpoint。
2. 经用户确认费用后执行 Wan3 480P、2 秒、无水印最小任务。
3. 持久化 Wan3 task_id，验证进程重启后继续轮询而不重复提交。
4. 安装并固定 FFmpeg/ffprobe 支持版本。
5. 生成 2-3 个片段，统一编码/帧率/尺寸后合成。
6. 资产登记 sha256、MIME、大小、Provider、模型、参数和 source_asset_ids。
7. 前端提供图片、片段、成片预览与下载。
8. 记录耗时、调用次数、错误、输出分辨率和估算成本。

出口标准：Qwen Image → Wan3 → FFmpeg 输出可播放 MP4；任一镜头可回溯文本、图片和视频。

### Sprint N+2：Agent 与产品体验（预计 2 周）

1. Node Manifest 成为前后端与 Agent 的单一事实来源。
2. Agent generate/modify 使用结构化输出并先返回 preview。
3. 前端展示 GraphPatch diff、有损警告、确认和撤销。
4. TemplateSelector 装载 API 返回的 WorkflowSpec。
5. Provider 设置持久化；秘密只保存引用。
6. 拆分 workflowStore/executionStore，接入 WebSocket 和断线补拉。
7. 增加工作流列表、导入导出、执行历史和资产页面。
8. 建立 20+ 中文 Agent golden cases。

出口标准：用户能自然语言创建/修改流程并确认；刷新/重启后工作流、模板、非秘密设置和执行状态一致。

### Sprint N+3：Release Candidate（预计 1-2 周）

1. Playwright 覆盖编辑、运行、失败、重试、刷新、Agent 和下载。
2. Windows/macOS/Linux CI matrix。
3. SSRF、路径穿越、密钥脱敏、超大文件和 prompt injection 测试。
4. DB 备份/恢复、磁盘满、Provider 超时和 Worker 崩溃演练。
5. 100 节点画布、4 Worker、API P95 和内存基准。
6. 安装、升级、回滚、故障排查和局域网开放说明。

出口标准：Active 计划 Release Checklist 全绿，才允许标记 v1.0 RC。

## 10. 下一批可直接领取的工单

| 顺序 | 工单 | 交付 | 依赖 |
|---:|---|---|---|
| 1 | AVC-201 | NodeResult/ArtifactRef Schema | 无 |
| 2 | AVC-105 | node_runs/external_job_id 迁移与 Repository | 201 |
| 3 | AVC-203 | scene_id 动态 map 和输入组装 | 105,201 |
| 4 | AVC-204 | 递归失败传播与执行不变量 | 203 |
| 5 | AVC-205 | 取消竞态和状态条件更新 | 105 |
| 6 | AVC-207 | 2-4 Worker pool 与原子 claim | 204 |
| 7 | AVC-302/303 | WebSocket executionStore 与重连 | 204 |
| 8 | AVC-308 | Mock 浏览器 E2E | 203-207,302/303 |
| 9 | AVC-508 | Wan3 external job 持久化和 UAT | 105,203 |
| 10 | AVC-403/406 | FFmpeg normalize 与真实媒体测试 | 308 |

在 AVC-308 通过之前，暂停新增 Provider、节点种类、条件分支、通用循环、cron 和插件 SDK。

## 11. 文档治理

- 本文件每个 Sprint Demo 后更新一次，测试数字必须来自同次运行。
- `docs/plans/2026-09-15-company-delivery-plan.md` 是唯一 Active 开发计划。
- `docs/plans/phase-c-plan.md`、`phase-d-plan.md`、`phase-e-plan.md` 仅为历史文档。
- Provider 官方参数分别维护在 `docs/integrations/`。
- PRD 只写产品需求，dp 只写目标架构；实现现状只写在本文件。
- 任何“完成”必须同时有代码、自动测试、主路径接入和验收证据。
