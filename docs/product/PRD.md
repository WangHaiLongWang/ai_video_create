# ai_video_create 产品需求文档

> 产品阶段：v1.0
> 文档职责：描述用户价值、产品范围和验收要求
> 实现状态：见 [`../PROJECT-STATUS.md`](../PROJECT-STATUS.md)
> 排期：见 [`../plans/active/DELIVERY-PLAN.md`](../plans/active/DELIVERY-PLAN.md)

## 1. 产品定位

ai_video_create 是一个本地优先、可视化编排 AI 内容生成流程的桌面级 Web 平台。

用户通过节点和连线定义 AI 流水线，平台负责编译、调度、恢复和产物管理。内置“提示词 → 分镜 → 图片 → 视频 → 合成”模板，支持自然语言 Agent 生成或修改工作流。

### 核心价值

- **本地优先**：无需 Docker、Redis、PostgreSQL 或对象存储。
- **Provider 可替换**：文本、图像、视频能力分别选择本地或云端后端。
- **可视化**：非技术用户可以查看数据流、进度、错误与产物。
- **可恢复**：长任务、失败重试和执行历史可追踪。
- **可解释**：每个最终视频可以追溯到 scene、图片、视频片段和模型参数。

## 2. v1.0 Provider 基线

| 能力 | 默认 Provider/模型 | 默认参数 | 备选 |
|---|---|---|---|
| 文本/分镜 | Xiaomi MiMo / `mimo-v2.5-pro` | OpenAI-compatible Chat Completions | Mock / Ollama / OpenAI |
| 文生图 | DashScope / `qwen-image-3.0` | 1280×720、提示词增强、无水印 | OpenAI / ComfyUI |
| 图生视频 | Bailian / `wan3.0-video` | 480P、adaptive、5 秒、音轨开启 | Prime / ComfyUI / Mock |
| 视频拼接 | 本地 FFmpeg | MP4 | 无 |

说明：Wan3 是百炼云端 Provider，不属于 ComfyUI。480P 是项目开发默认，Wan3 API 官方默认分辨率是 1080P。

## 3. 目标用户

| 用户 | 场景 | 核心诉求 |
|---|---|---|
| 内容创作者 | 批量生产短视频 | 提示词出片、可视化调参、失败重试 |
| AI 工程师 | 验证多模型流水线 | 切换 Provider、查看输入输出和日志 |
| 产品经理 | 演示 AI 能力 | 使用模板或 Agent 快速生成流程 |
| 教育者 | 讲解 AI 工作流 | 直观展示 DAG、数据流和产物关系 |

## 4. v1.0 功能范围

### 4.1 工作流编辑器（P0）

| 功能 | 要求 | 验收 |
|---|---|---|
| 节点添加 | 从节点库加入画布 | 位置正确，可继续拖动 |
| 节点连线 | 输出 handle 到兼容输入 handle | 非法类型被拒绝并说明原因 |
| 节点配置 | 右侧面板编辑模型和参数 | 保存后刷新可恢复 |
| 删除 | Delete/Backspace | 相关边同步删除 |
| 画布导航 | 缩放、平移、小地图 | 100 节点仍可操作 |
| 撤销/重做 | Ctrl/Cmd+Z、Shift+Z/Y | 至少 20 个语义步骤 |
| 保存 | SQLite + 乐观锁 | 冲突不静默覆盖 |
| 导入导出 | WorkflowSpec JSON | roundtrip 结构等价 |
| 多端口 | 节点可声明多个命名输入/输出 | Handle ID、类型和基数保存后不丢失 |
| 连线校验 | 类型、方向、基数、自环、重复边和环检测 | 前端即时提示，后端权威拒绝 |
| Edge 语义 | direct/map/aggregate | 映射模式、顺序和标签可保存、迁移 |
| 自定义字段 | 添加、重命名、排序和删除配置字段 | 类型校验、Undo、导入导出一致 |
| 自定义端口 | 高级模式添加/删除命名端口 | 删除端口前显示关联边并确认 |

### 4.2 节点类型（P0）

| 节点 | 输入 | 输出 | 关键配置 |
|---|---|---|---|
| 文本输入 | 无 | `text` | prompt |
| 分镜生成 | `text` | `list<scene>` | Provider、模型、scene 数、风格 |
| 文生图 | `scene` | `image` | Provider、模型、尺寸、seed、提示词增强 |
| 图生视频 | `image` | `video` | Provider、模型、分辨率、比例、时长、音频、seed、水印 |
| 视频拼接 | `list<video>` | `video` | 编码、尺寸、帧率、转场、输出格式 |
| 输出 | 任意资产 | 无 | 预览、下载、文件名 |

默认短视频链路使用结构化 scene，不依赖普通字符切段：

```json
{
  "scene_id": "scene-001",
  "index": 0,
  "narration": "...",
  "image_prompt": "...",
  "video_prompt": "...",
  "duration_seconds": 5
}
```

### 4.3 执行与监控（P0）

| 功能 | 要求 |
|---|---|
| 一键执行 | 保存并验证工作流，创建不可变执行快照 |
| DAG 调度 | 拓扑、scene map、aggregate、依赖和终态收敛 |
| 状态 | waiting/running/completed/failed/skipped/cancelled |
| 实时进度 | WebSocket 通知，轮询兜底，断线补拉 |
| 预览 | 节点内或资产页展示图片/视频 |
| 历史 | 查询执行、任务、错误、耗时和参数 |
| 重试 | 单节点/单 scene item，不重复已成功资产 |
| 取消 | 不接受晚到结果，外部任务尽可能取消 |
| 恢复 | Worker/进程重启后继续或明确失败 |

### 4.4 Provider 管理（P0）

- 展示 text/image/video capability。
- 新增或编辑 Base URL、模型和非秘密参数。
- Key 不通过 GET 返回，不进入工作流或导出文件。
- 支持连通性测试和模型列表（协议支持时）。
- 支持节点级 Provider/模型覆盖。
- 设置持久化后重启恢复。

### 4.5 Workflow Agent（P0）

- 从自然语言生成候选 WorkflowSpec。
- 修改现有工作流并返回 GraphPatch。
- 在应用前展示 diff、warnings 和 destructive 标记。
- 任何输出必须经过后端 Schema、端口、DAG 和安全校验。
- 应用 patch 使用 expected_version。
- 无可用 LLM 时降级为确定性模板，不伪装为智能生成。
- Agent 基于 Node Manifest 和模板工具生成 WorkflowIntent，由后端编译为 WorkflowSpec 2.0；不让 LLM直接猜测 UUID、Handle 或布局坐标。

### 4.6 模板（P1）

官方模板：

```text
TextInput → Storyboard → TextToImage × N
          → ImageToVideo × N → VideoConcat → Output
```

支持浏览、搜索、应用和保存自定义模板。应用后返回的 WorkflowSpec 必须立即装入画布。

### 4.7 资产（P1）

- 按 image/video/final 分类展示。
- 预览、单个下载和批量下载。
- 记录 execution、node、task、scene、Provider、模型、参数、SHA-256 和 source assets。
- 被引用资产不能直接删除。
- 清理先 dry-run，防止误删。

### 4.8 Scene Prompt 管理（P0）

- 将 Storyboard 实际结果保存为版本化 Scene Prompt Bundle。
- 支持逐镜编辑 narration、image_prompt、video_prompt、时长和 Provider 参数。
- 支持锁定 scene，重新生成时不覆盖用户修改。
- 支持 JSON、Markdown、CSV、纯文本导入导出。
- 支持 Qwen Image 与 Wan3 JSONL 请求预览，不包含 Key、签名 URL或绝对路径。
- Workflow 定义导出与 Scene 运行数据导出必须分离。

## 5. 核心用户流程

### 5.1 从提示词生成视频

```text
打开平台
  → 选择官方模板或让 Agent 生成
  → 输入主题和镜头数
  → 选择文本/图像/视频 Provider
  → 检查预计调用数量和成本
  → 运行
  → 查看 scene/item 进度
  → 处理失败或取消
  → 预览并下载最终视频
  → 回溯任一镜头的文本、图片和片段
```

### 5.2 修改 Provider

```text
打开设置
  → 选择 capability
  → 填写 Base URL、模型和 Key
  → 测试连接
  → 保存
  → 在节点选择默认或覆盖 Provider
  → 重新执行
```

### 5.3 Agent 修改工作流

```text
输入“改成 9:16、6 个镜头并开启音轨”
  → Agent 返回 GraphPatch preview
  → 用户查看新增/更新/删除项
  → 确认应用
  → 画布作为一个可撤销步骤更新
```

## 6. 非功能要求

| 维度 | v1.0 要求 |
|---|---|
| 启动 | 本地冷启动 < 5 秒，不含外部模型 |
| 并发 | 2-4 Worker，无重复 claim |
| 数据 | SQLite 单文件，可备份、迁移、恢复 |
| 网络 | Mock 模式完全离线 |
| 平台 | Windows、macOS、Linux |
| 浏览器 | 最新 Chrome/Edge/Safari；自动化覆盖 Chromium |
| 安全 | 默认 127.0.0.1，Key 不进日志/DB 普通字段/导出 |
| 性能 | 100 节点编译 P95 < 100ms；非 AI API P95 < 100ms |
| 恢复 | 无永久 pending；长任务不重复计费提交 |
| 可访问性 | 键盘操作、焦点可见、状态不只依赖颜色 |

## 7. 数据要求

核心实体：

- Workflow：可编辑定义、schema version 和乐观锁版本。
- Execution：不可变 workflow snapshot 和最终状态。
- Task/NodeRun：输入、结果、attempt、lease、external job 和错误。
- ExecutionEvent：可补拉的有序事件。
- Asset：本地文件、媒体元数据和血缘。
- ProviderConfig：非秘密配置和 secret reference。
- Template：内置/自定义模板和版本。

具体表结构属于架构文档和迁移，不在 PRD 中复制 SQL。

## 8. v1.0 发布验收

1. Mock 完整链路无网络运行成功。
2. MiMo → Qwen Image → Wan3 → FFmpeg 最小真实链路可重复。
3. scene 文本、图片、片段和最终视频一一关联。
4. 失败、重试、取消、刷新、断线和进程重启状态一致。
5. Windows/macOS/Linux smoke 通过。
6. 前端 unit/type/build/E2E 和后端 unit/integration 全绿。
7. 安全、备份恢复、升级回滚文档和演练通过。

### 8.1 指定真实验收工作流

“冬季单板滑雪教学”作为首条内容质量验收：一个逻辑 Scene 生成两张写实照片，每张照片生成 3 秒视频，默认拼接为约 6 秒成片。人数、左右位置、固定器状态、单板姿态和背景无人是硬约束。具体 Prompt、任务 fan-out、资产血缘和 UAT 标准见 [`../plans/active/SKI-LESSON-WORKFLOW-PLAN.md`](../plans/active/SKI-LESSON-WORKFLOW-PLAN.md)。

## 9. v1.0 不做

- 多用户、RBAC、实时协作和云端横向扩容。
- 任意 Python/JavaScript 执行节点和插件市场。
- 通用条件分支、嵌套循环和 cron。
- 专业时间线、配音、字幕和音频混音。
- 为所有云厂商提供专用适配器。

## 10. 主要风险

| 风险 | 影响 | 对策 |
|---|---|---|
| SQLite 写竞争 | 任务领取/状态延迟 | WAL、短事务、原子 claim、压力测试 |
| 长视频任务 | 超时、重复计费 | external job ID、恢复轮询、幂等提交 |
| 外部协议变化 | Provider 失败 | Contract Test、错误归一化、版本锁定 |
| 磁盘耗尽 | 资产写入失败 | 空间预检、配额、dry-run 清理 |
| FFmpeg 差异 | 合成不可播放 | 固定版本、normalize、三平台媒体测试 |
| Agent 非法图 | 数据损坏或有损修改 | 结构化输出、后端校验、diff 和确认 |
| API 成本 | 批量调用超预算 | 调用量/成本预估、并发上限、用户确认 |
