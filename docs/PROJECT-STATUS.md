# ai_video_create 项目状态

> 基线日期：2026-09-16
> 状态版本：9.0
> Active 计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)
> 评估原则：只采用当前环境可重复结果；历史报告单独列为证据，不替代当前门禁。

## 1. 结论

项目已完成主要产品模块和执行器骨架，处于“内部验收前的集成收敛期”，不是可发布 RC。

已经具备：

- React Flow 工作流编辑与持久化；
- NodeResult/ArtifactRef、scene map、Scheduler、RetryPolicy、WorkerPool；
- REST + WebSocket 执行监控；
- MiMo、Qwen Image、Wan3、ComfyUI、OpenAI、Ollama、Mock Provider；
- Agent preview/diff 和模板装载；
- Asset/Template 数据表与 API；
- Wan3 与 FFmpeg 的独立验收报告；
- GitHub Actions、Playwright 和 release-check 基础设施。

当前发布门禁状态：

1. ✅ Vitest 已隔离 `e2e/`，前端 105 项通过。
2. ✅ TypeScript 和生产构建通过。
3. ✅ Node 20.19.0 满足 Playwright 版本要求。
4. ❌ Pillow 未安装到当前 venv，完整后端测试收集失败。
5. ⚠️ FFmpeg 报告在另一 Python 环境通过，当前 venv 仍需复现。
6. ⚠️ CI/Playwright 文件存在，但本次未取得同一 commit 的三平台绿色证据。
7. ⚠️ React Flow 已有多端口/Handle ID/图校验基础，仍缺连线错误 UI、Edge 编辑和主入口强制校验。
8. ⚠️ Scene Bundle/导出 API 已有基础，仍缺 SQLite Draft、Scene Editor 和下载式产品交互。

### 当前评分

| 维度 | 完成度 | 判断 |
|---|---:|---|
| 架构骨架 | 90% | 分层完整，共享图/Scene Schema 待补 |
| React Flow 编辑器 | 72% | 多端口和校验基础已实现，交互反馈/Edge 编辑待完成 |
| Mock 用户链路 | 90% | 执行器成熟，完整后端门禁仍被依赖阻断 |
| 真实多模态 | 78% | MiMo/Qwen/Wan3 有真实证据，FFmpeg 当前环境待复现 |
| Agent 与模板 | 82% | preview/diff/装载、Scene Schema/导出器已接入，编辑器缺失 |
| 发布工程 | 65% | 前端绿色，完整后端/媒体/三平台证据不足 |
| 综合产品完成度 | **约 81%** | 内部验收阶段，不是 RC |

## 2. 当前可重复测试基线

当前本机：Windows、Node 20.19.0、npm 10.8.2、Python 3.12.3。

| 验证项 | 结果 | 状态 |
|---|---:|---|
| 前端 Vitest (8 files) | 105 passed | ✅ 通过 |
| TypeScript typecheck | 0 errors | ✅ 通过 |
| Vite production build | 493.02KB JS / gzip 144.22KB | ✅ 通过 |
| 后端核心（排除 integration） | 504 passed、7 skipped | ✅ 通过 |
| 后端完整 pytest | Pillow 缺失，Wan3 UAT 收集失败 | ❌ 失败 |
| 根 `npm test` | 前端通过，后端收集失败 | ❌ 失败 |
| Playwright | Node 已满足；本次未运行浏览器套件 | ⚠️ 未验证 |

### 报告可追溯性说明

- [`reports/wan3-uat.md`](reports/wan3-uat.md) 记录了真实 Wan3 任务和 MP4 下载。
- [`reports/ffmpeg-integration.md`](reports/ffmpeg-integration.md) 使用系统外另一个 Python 环境中的 imageio-ffmpeg。
- 两份报告日期为 2026-09-17，晚于当前基线日期 2026-09-16；应由报告作者确认日期并补充 commit、环境锁文件和原始测试输出。

## 3. 默认运行配置

```text
LLM       openai_compat / Xiaomi MiMo / mimo-v2.5-pro
Image     dashscope / qwen-image-3.0 / 1280x720
Video     wan3 / wan3.0-video / 480P / adaptive / 5s
Local     ComfyUI 可选（img2vid workflow 仍需真实节点模板）
Storage   data/assets
Database  data/ai_video_create.db
Host      127.0.0.1
```

配置与 Provider 说明：

- [`integrations/mimo-v2.5-pro.md`](integrations/mimo-v2.5-pro.md)
- [`integrations/qwen-image-3.0.md`](integrations/qwen-image-3.0.md)
- [`integrations/wan3-video.md`](integrations/wan3-video.md)

## 4. 功能完成矩阵

### 4.1 编辑器与工作流

| 能力 | 状态 | 缺口 |
|---|---|---|
| 画布移动/缩放/连线/删除 | 已实现 | 浏览器连线矩阵仍需专项 E2E |
| 节点添加 | 已实现 | 支持点击和侧栏拖入 |
| 属性配置 | 已实现 | 手写 key/value，非 Node Manifest/Schema 表单 |
| Undo/Redo | 已实现 | 拖动过程可能产生过多历史项 |
| localStorage | 已实现 | 只维护当前工作流 |
| SQLite CRUD/乐观锁 | 已实现 | Update body 仍需强类型收紧 |
| 工作流导入/导出 | 已实现 | 仅 WorkflowSpec 1.0，无 Scene Prompt 导出 |
| 自动保存 | 部分 | 失败只进 console，保存文案可能误导 |
| Handle/端口 | 基础实现 | Node Manifest、多命名 Handle、port label/type 已有 |
| 连线验证 | 基础实现 | 前后端覆盖类型/方向/基数/自环/重复边/环；UI 仅 console 提示 |
| Edge 语义 | 部分 | EdgeData 有 direct/map/aggregate 字段，缺编辑器与执行语义统一验收 |
| 图版本迁移 | 基础实现 | WorkflowSpec 2.0 和 1.0 migration 已有，viewport 保存主路径待验收 |
| Scene Bundle | 基础实现 | TS/Pydantic、materializer、导出器和安全扫描已有 |
| Scene Draft | 部分 | API/Service 已有但仅内存存储，重启丢失 |
| Scene 编辑器 | 未实现 | 无可视化逐镜/批量编辑 UI |
| Scene/Prompt 导入导出 | 后端基础实现 | JSON/Markdown/CSV/Text/Qwen/Wan3 已有，缺下载 UI/E2E |

### 4.2 执行引擎

| 能力 | 状态 | 证据/缺口 |
|---|---|---|
| NodeResult/ArtifactRef | 已实现 | contracts tests |
| Storyboard scene map | 已实现 | scene mapping integration tests |
| 上游结果注入 | 已实现 | Scheduler/Worker |
| 深层失败传播 | 已实现 | failure propagation tests |
| 取消竞态防护 | 已实现 | 状态条件更新 |
| RetryPolicy | 已实现 | retry tests + Migration 007 |
| external_job_id | 已实现 | Migration 006 + persistence tests |
| WorkerPool | 已实现 | worker pool tests |
| 执行收敛 | 已实现 | Scheduler/queue tests |
| 节点级手动重试 | 已实现 | executionStore 调用 retry API并更新节点状态 |
| 长任务重启续轮询 | 部分 | ID 持久化已完成，恢复编排仍需端到端验证 |
| 正式 schema migration 表 | 未实现 | 当前按 SQL 文件执行并忽略重复列 |

### 4.3 前端执行、Agent 和模板

| 能力 | 状态 | 缺口 |
|---|---|---|
| REST 启动/取消/轮询 | 已实现 | 错误态仍需统一 |
| WebSocket 重连/补拉 | 已实现 | 单元测试通过，浏览器断线 E2E 待补 |
| ExecutionPanel | 已实现 | retry API/UI 已接通，仍需浏览器 E2E |
| Agent generate preview | 已实现 | 严格工具调用/Schema constrained output 待加强 |
| GraphPatch diff/warning | 已实现 | 有损操作和 expected_version 需完整 UAT |
| TemplateSelector 装载 | 已实现 | API 返回 spec 已装入画布，缺浏览器 E2E 证据 |
| Provider 设置 | 已实现 | API 只改内存，重启以 `.env` 为准 |
| 自定义 LLM | 已实现 | 单配置槽，尚非多 Provider CRUD |
| 资产预览/下载页 | 已实现基础版 | AssetPanel 有列表/筛选/预览/下载/删除 |
| 工作流列表 | 已实现基础版 | WorkflowListPage 有搜索/加载/删除/导入导出 |

### 4.4 Provider 与媒体

| Provider/服务 | 状态 | 缺口 |
|---|---|---|
| Xiaomi MiMo | 真实调用通过 | 无自动外部 smoke 门禁 |
| Qwen Image 3.0 | 真实生图通过 | 多镜头成本/UAT 待完善 |
| Wan3.0 Video | 报告记录真实 UAT | 当前 venv 缺 Pillow，无法复现完整套件 |
| OpenAI | 适配器与 Contract | 未配置真实 Key UAT |
| Ollama | 适配器 | 本机服务未验证 |
| ComfyUI T2I | 基础 workflow | 本机服务未验证 |
| ComfyUI I2V | 占位 | 不可用于生产 |
| FFmpeg | 实现已增强 | 当前路径不可用，依赖未声明 |

## 5. 架构实现评估

### 5.1 优点

- API、Engine、Handler、Provider、Repository 和 Service 边界已经形成。
- 图像、视频、文本 Provider 按 capability 分离，Wan3 未混入 ComfyUI。
- 执行结果、外部 Job ID、重试字段和资产血缘均进入 SQLite。
- 前端工作流状态和 executionStore 开始拆分。
- 真实 Provider 与离线 Contract Test 并存，方向正确。
- 安全默认监听 127.0.0.1，Settings API 不返回 Key。

### 5.2 架构债务

1. **共享契约仍分散**：Node 类型/配置仍在前端、模型、Agent 各自维护。
2. **迁移器不够正式**：无 `schema_migrations`，靠 duplicate column 容错。
3. **配置持久化不足**：设置页只改内存，未落 ProviderConfig/secret reference。
4. **队列事务需压力验证**：claim 的 SELECT/BEGIN 时序仍需多连接并发证明。
5. **资产安全需收紧**：路径 root、原子写、MIME/大小和引用删除策略需统一验收。
6. **图契约仍有双实现**：前后端 Manifest/validator 各自维护，需要共用 fixtures 或代码生成。
7. **Scene 数据产品层未完成**：Schema 与导出器已存在，但 Draft 仅内存、无 Scene Editor 和下载交互。
8. **外部任务恢复证据不足**：Wan3 ID 可保存，但重启恢复的完整状态机和 UI 仍需端到端验证。

## 6. 发布阻断清单

| ID | 阻断项 | 优先级 | 关闭标准 |
|---|---|---:|---|
| R0-1 | 完整后端测试缺 Pillow | P0 | requirements 安装后完整 pytest 可收集 |
| R0-2 | FFmpeg 路径不可复现 | P0 | venv 声明依赖或系统安装；integration 19/19 当前环境通过 |
| R0-3 | 三平台 CI 未提供本次 run 证据 | P0 | 同一 commit Windows/macOS/Linux 全绿 |
| R0-4 | Playwright 未执行本次基线 | P0 | Chromium 核心 E2E 通过并归档 |
| R0-5 | React Flow 产品交互未闭环 | P0 | 连线错误 UI、Edge 编辑、viewport、E2E 完成 |
| R0-6 | Scene Prompt 产品层未闭环 | P0 | SQLite Draft、Editor、下载导出和 E2E 完成 |
| R0-7 | 报告元数据不一致 | P1 | 校正日期，记录 commit、环境、命令和原始输出 |

## 7. 里程碑

| 里程碑 | 当前状态 | 下一出口 |
|---|---|---|
| M0 工程基线 | 部分绿色 | 完整后端 pytest + Playwright + 三平台证据 |
| M1 编辑闭环 | 基础完成 | WorkflowSpec 2.0、多端口/边语义、Scene 导出 |
| M2 Mock 执行闭环 | 基本完成 | 浏览器 E2E 和重启恢复证据 |
| M3 真实多模态 | 有历史 UAT | 待锁定环境复现 Qwen/Wan3/FFmpeg |
| M4 Agent/模板 | 功能已接入 | E2E + 结构化工具 + 设置持久化 |
| M5 Release Candidate | 未达到 | 所有发布阻断关闭后重新运行 Release Check |

## 8. 下一阶段计划

### 专项 F1：React Flow 端口图契约（2 周）

1. Node Manifest 与稳定 Port ID。
2. 多输入/多输出 Handle 渲染。
3. 类型、方向、cardinality、required、自环、重复边和环检测。
4. Edge mode：direct/map/aggregate，保存 sourceHandle/targetHandle。
5. WorkflowSpec 2.0、viewport 和 1.0 migration。
6. 连线兼容端口高亮、失败原因、重连与键盘可访问性。

出口：复杂节点能够可靠连线，旧工作流无损迁移，前后端验证结果一致。

### 专项 F2：Scene Prompt Bundle（2 周）

1. 冻结 Scene Prompt Bundle JSON Schema。
2. 将 execution Storyboard 结果 materialize 为 Bundle。
3. Scene draft/override/lock 持久化。
4. Scene Editor 支持逐镜和批量编辑。
5. JSON、Markdown、CSV 和纯文本导入导出。
6. 导出内容扫描 Key、签名 URL 和绝对路径。

出口：用户可编辑、锁定、导出、导入 Scene，并保持 scene_id 与顺序稳定。

### 专项 F3：Provider Prompt 与发布门禁（1-2 周）

1. Qwen Image JSONL 请求预览。
2. Wan3 JSONL 请求预览，first frame 使用 Asset ID。
3. 画布 viewport、语义 Undo/Redo、复制粘贴和自动布局。
4. React Flow 连线和 Scene 导入导出 Playwright E2E。
5. 补齐 Pillow/FFmpeg 当前环境依赖并运行完整 pytest。
6. 同一 commit 三平台 CI、Playwright、Release Check 全绿。

出口：专项计划验收通过后，重新评估 `v1.0.0-rc.1`。

详细工单、Schema 和验收场景见：

- [`plans/active/FRONTEND-FLOW-SCENE-PLAN.md`](plans/active/FRONTEND-FLOW-SCENE-PLAN.md)
- [`plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](plans/active/SKI-LESSON-WORKFLOW-PLAN.md)

## 9. 文档治理

- 文档入口：[`README.md`](README.md)。
- 产品需求：[`product/PRD.md`](product/PRD.md)。
- 架构：[`architecture/SYSTEM-DESIGN.md`](architecture/SYSTEM-DESIGN.md)。
- Active 计划：[`plans/active/DELIVERY-PLAN.md`](plans/active/DELIVERY-PLAN.md)。
- 历史计划只放 `plans/archive/`，不用于完成度判断。
- Provider 配置放 `integrations/`；测试证据放 `reports/`。
- 状态数字必须来自同一环境、同一 commit、同一次命令。
